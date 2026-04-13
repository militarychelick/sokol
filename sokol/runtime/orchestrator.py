"""Main orchestrator - agent event loop."""









import asyncio




import signal




import threading




import time




from typing import Any, Callable, Optional









from sokol.core.config import Config, get_config




from sokol.core.types import AgentEvent, AgentState, EventType




from sokol.observability.logging import get_logger, setup_logging




from sokol.runtime.events import EventBus




from sokol.runtime.state import AgentStateMachine




from sokol.runtime.tasks import TaskManager




from sokol.runtime.intent import RuleBasedIntentHandler, Intent




from sokol.runtime.router import IntentRouter, ProposedAction, DecisionSource, ToolChain, ToolChainStep, ConditionEvaluator




from sokol.runtime.response import ResponseBuilder, AgentResponse, ResponseMode, ResponseFormatter




from sokol.runtime.stability import StabilityChecker, StabilityReport




from sokol.runtime.tool_intelligence import ToolIntelligenceEngine




from sokol.runtime.tool_registry import ToolRegistry




from sokol.runtime.control import ControlLayer, ControlDecision, RiskLevel




from sokol.runtime.observability import TraceCollector




from sokol.runtime.planning import PlanGenerator




from sokol.runtime.recovery import FailureRecovery




from sokol.runtime.ux_realness import UXRealness, ExecutionState




from sokol.runtime.user_model import UserModel




from sokol.runtime.memory_layer import MemoryLayer




from sokol.runtime.hardening import HardeningEngine




from sokol.runtime.task_layer import TaskManager




from sokol.runtime.tool_contract import ToolContractNormalizer




from sokol.runtime.decision_trace import DecisionTraceCollector




from sokol.runtime.intent_model import IntentExtractor, ContextCompressionEngine




from sokol.integrations.llm import LLMManager, LLMMessage




from sokol.tools.registry import get_registry




from sokol.memory.events import MemoryEvent, MemoryEventSanitizer









logger = get_logger("sokol.runtime.orchestrator")









# Watchdog timeout for stuck states (seconds)




WATCHDOG_TIMEOUT = 30.0














class Orchestrator:




    """




    Main orchestrator for the agent.









    Coordinates:




    - State machine




    - Event bus




    - Task manager




    - Emergency stop




    """









    def __init__(self, config: Config | None = None) -> None:




        self._config = config or get_config()




        self._state_machine = AgentStateMachine()




        self._event_bus = EventBus()









        # Unified intent router (replaces LLM + intent handler)




        self._intent_router = IntentRouter()




        self._tool_registry = get_registry()









        # Set emergency stop callback on tool registry




        self._tool_registry.set_emergency_stop_callback(self._is_emergency_triggered)









        # Confirmation manager for dangerous actions




        from sokol.safety.confirm import ConfirmationManager




        self._confirmation_manager = ConfirmationManager()









        # Conversation history (for LLM context)




        self._conversation_history: list[LLMMessage] = []









        # Watchdog state tracking




        self._state_enter_time: float = 0.0




        self._watchdog_running = False




        self._watchdog_thread: threading.Thread | None = None




        self._lock = threading.Lock()









        # Wire state machine to event bus




        self._state_machine.set_event_callback(self._on_state_change)









        # Running state




        self._running = False




        self._main_loop: asyncio.AbstractEventLoop | None = None




        self._shutdown_event = threading.Event()




        self._response_builder = ResponseBuilder()




        self._response_formatter = ResponseFormatter()




        self._failure_recovery = FailureRecovery()









        # Memory & User Model layer (personalization)




        self._user_model = UserModel()









        # Tool Registry Normalization Layer (semantic tool graph)




        self._tool_registry_normalization = ToolRegistry()









        # Task Layer (task/goal system) - single instance




        self._task_manager = TaskManager()









        # Intent Model Layer (intent extraction and context compression) - initialize before MemoryLayer




        self._intent_extractor = IntentExtractor()




        self._context_compression_engine = ContextCompressionEngine()









        # Memory layer (with tool registry, task manager, and context compression engine)




        self._memory_layer = MemoryLayer(




            self._user_model,




            tool_registry=self._tool_registry_normalization,




            task_manager=self._task_manager,




            context_compression_engine=self._context_compression_engine




        )




        self._memory_manager: Any = None  # MemoryManager reference (optional)




        self._memory_sanitizer = MemoryEventSanitizer()




        self._stability_checker = StabilityChecker()




        self._tool_intelligence = ToolIntelligenceEngine(tool_registry=self._tool_registry_normalization)




        self._condition_evaluator = ConditionEvaluator()




        self._control_layer = ControlLayer(




            tool_registry=self._tool_registry_normalization,




            task_manager=self._task_manager




        )




        self._trace_collector = TraceCollector()




        self._plan_generator = PlanGenerator()









        # System Hardening Layer (runtime invariants and self-checks)




        self._hardening_engine = HardeningEngine()









        # Tool Execution Contract Layer (strict tool interaction standardization)




        self._tool_contract_normalizer = ToolContractNormalizer()









        # Decision Trace Layer (explainability for system decisions)




        self._decision_trace_collector = DecisionTraceCollector()









        # UX Realness Layer (presentation state)




        self._ux_realness = UXRealness()









        # Pending action for confirmation (runtime only, not persistent)




        self._pending_action: ProposedAction | None = None




        self._pending_control_result: Any | None = None









        # Callbacks




        self._on_input_callback: Callable[[str], None] | None = None




        self._on_response_callback: Callable[[str], None] | None = None




        self._on_confirm_callback: Callable[[Any], bool] | None = None









        # Optional preprocessing callback for perception adapters (defaults to passthrough)




        self._preprocess_callback: Callable[[str], str] | None = None









        # Register emergency stop handler




        self._event_bus.subscribe(




            EventType.EMERGENCY_STOP,




            self._handle_emergency_stop,




        )









    @property




    def state(self) -> AgentState:




        """Current agent state."""




        return self._state_machine.state









    @property




    def state_machine(self) -> AgentStateMachine:




        """State machine instance."""




        return self._state_machine









    @property




    def event_bus(self) -> EventBus:




        """Event bus instance."""




        return self._event_bus









    @property




    def task_manager(self) -> TaskManager:




        """Task manager instance."""




        return self._task_manager









    def setup(self) -> None:




        """Setup logging and other infrastructure."""




        setup_logging(




            level=self._config.logging.level,




            log_file=self._config.logging.file,




            max_size=self._config.logging.max_size,




            backup_count=self._config.logging.backup_count,




            use_json=self._config.logging.format == "json",




        )









        logger.info_data(




            "Orchestrator setup complete",




            {




                "agent_name": self._config.agent.name,




                "llm_provider": self._config.llm.provider,




            },




        )









    def start(self) -> None:




        """Start the orchestrator."""




        if self._running:




            logger.warning("Orchestrator already running")




            return









        self._running = True




        self._shutdown_event.clear()









        # Start watchdog




        self._start_watchdog()









        logger.info("Orchestrator started")









        # Setup signal handlers




        self._setup_signal_handlers()









    def stop(self, reason: str = "shutdown") -> None:




        """Stop the orchestrator."""




        if not self._running:




            return









        logger.info_data("Orchestrator stopping", {"reason": reason})









        # Stop watchdog




        self._stop_watchdog()









        # Cancel all tasks




        self._task_manager.cancel_all(reason)









        # Set shutdown event




        self._shutdown_event.set()









        self._running = False









        # Force transition to idle




        self._state_machine.force_transition(AgentState.IDLE, reason)









    def _start_watchdog(self) -> None:




        """Start watchdog thread to monitor for stuck states."""




        if self._watchdog_running:




            return









        self._watchdog_running = True




        self._watchdog_thread = threading.Thread(




            target=self._watchdog_loop, daemon=True, name="Watchdog"




        )




        self._watchdog_thread.start()




        logger.info("Watchdog started")









    def _stop_watchdog(self) -> None:




        """Stop watchdog thread."""




        self._watchdog_running = False




        if self._watchdog_thread:




            self._watchdog_thread.join(timeout=2.0)




        logger.info("Watchdog stopped")









    def _watchdog_loop(self) -> None:




        """Watchdog loop that monitors state for stuck conditions."""




        while self._watchdog_running:




            time.sleep(1.0)









            with self._lock:




                current_state = self._state_machine.state









                # Check if in a busy state for too long




                if current_state != AgentState.IDLE:




                    elapsed = time.time() - self._state_enter_time









                    if elapsed > WATCHDOG_TIMEOUT:




                        logger.error_data(




                            "Watchdog timeout - forcing state reset",




                            {"state": current_state.value, "elapsed": elapsed},




                        )



                        


                        


                        # Cancel any running tasks before state reset




                        active_task = self._task_manager.get_active_task()




                        if active_task:




                            self._task_manager.fail_task(active_task.task_id, reason="watchdog_timeout")




                            logger.warning_data("Task cancelled by watchdog",




                                {"task_id": active_task.task_id})




                        # Cancel all tasks to ensure clean state




                        self._task_manager.cancel_all("watchdog_timeout")



                        


                        


                        self._state_machine.force_transition(




                            AgentState.IDLE, "watchdog_timeout"




                        )




                        self._state_enter_time = time.time()









    def emergency_stop(self, reason: str = "user_triggered") -> None:




        """




        Emergency stop - immediately halt all activity.









        This is the critical safety feature.




        """




        logger.warning_data(




            "EMERGENCY STOP triggered",




            {"reason": reason, "current_state": self.state.value},




        )









        # Cancel ALL tasks immediately




        cancelled = self._task_manager.cancel_all(f"emergency_stop:{reason}")









        # Force state to idle




        self._state_machine.force_transition(AgentState.IDLE, "emergency_stop")









        # Emit emergency stop event




        self._event_bus.create_and_emit(




            EventType.EMERGENCY_STOP,




            "orchestrator",




            {"reason": reason, "tasks_cancelled": cancelled},




        )









    def _is_emergency_triggered(self) -> bool:




        """Check if emergency stop has been triggered."""




        from sokol.safety.emergency import get_emergency_handler




        handler = get_emergency_handler()




        return handler.is_triggered()







    def process_input(self, text: str, source: str = "user", screen_context: Optional[dict] = None) -> AgentResponse:



        """



        Process user input (text or voice transcription).







        Args:



            text: Input text



            source: Input source (user, voice, screen, etc.)



            screen_context: Optional screen context data from ScreenInputAdapter







        Strict execution loop:



        1. Validate input acceptance



        2. Check for confirmation/cancel commands (if pending action)



        3. Inject memory context (non-blocking)



        4. Transition to THINKING



        5. Execute LLM processing (with timeout)



        6. Parse and execute tools if needed



        7. Emit response



        8. Always return to IDLE or ERROR



        """


        if not self._state_machine.can_accept_input():


            logger.warning_data(
                "Input ignored - agent busy",
                {"state": self.state.value, "input": text[:50]},
            )


            return self._response_builder.build(
                final_text="Agent is busy, please try again.",
                success=False
            )


        logger.info_data(




            "Processing input",




            {"source": source, "text": text[:100]},




        )









        # Check for confirmation/cancel commands (if pending action exists)




        if self._pending_action is not None:




            text_lower = text.lower().strip()









            # Confirmation commands

            if text_lower in ["да", "подтверждаю", "выполняй"]:
                logger.info("User confirmed pending action")
                # Execute pending action and return response
                self._execute_pending_action()
                # Build confirmation response
                response = self._response_builder.build(
                    final_text="Действие выполнено.",
                    success=True
                )
                return response





            # Cancel commands




            elif text_lower in ["нет", "отмена", "стоп"]:




                logger.info("User cancelled pending action")




                self._pending_action = None




                self._pending_control_result = None









                # Send cancellation confirmation




                response = self._response_builder.build(




                    final_text="Действие отменено.",




                    tool_results=[],




                    success=False,




                    stability_score=1.0,




                    stability_flags=[],




                )




                # Format response based on mode (presentation layer)




                user_bias = memory_context_obj.user_bias if memory_context_obj else None




                mode = self._response_formatter.select_mode(source, user_bias)




                state = self._ux_realness.create_state(phase="finalizing")




                response = self._response_formatter.format(response, mode, state, context=text)

                self.emit_response(response)

                return response


        # Optional preprocessing (safe passthrough if not set)




        if self._preprocess_callback:




            text = self._preprocess_callback(text)









        # Intent Extraction: Extract structured intent from user input




        memory_context = self._get_memory_context()

        intent = None  # Default initialization to prevent UnboundLocalError

        try:
            intent = self._intent_extractor.extract_intent(text, memory_context)
        except Exception as e:
            intent = None
            logger.warning_data("Intent extraction failed, using default", {"error": str(e)})




        # Task Layer: Check if request relates to active task (use intent for better detection)




        active_task = self._task_manager.get_active_task()




        if active_task:




            # Use intent.task_related to inform continuation decision (but not control it)




            if self._task_manager.is_request_related_to_task(text, active_task):




                # Continue existing task




                self._task_manager.continue_task(active_task.task_id)



                task_related = intent.task_related if intent else False



                intent_type = intent.intent_type.value if intent else "unknown"




                task_related = intent.task_related if intent else False

                intent_type = intent.intent_type.value if intent else "unknown"

                logger.info_data(




                    "Continuing active task",



                    {"task_id": active_task.task_id, "goal": active_task.goal, "intent_task_related": task_related},



                )









                # Record task continuation decision trace




                from sokol.runtime.decision_trace import DecisionTrace, DecisionType




                decision_trace = DecisionTrace(




                    trace_id=self._decision_trace_collector.generate_trace_id(),




                    decision_type=DecisionType.TASK_CONTINUATION,



                    input_context={"request": text, "task_id": active_task.task_id, "intent_type": intent_type},



                    options_considered=["continue_task", "create_new_task"],




                    selected_option="continue_task",




                    confidence_score=0.7,  # Task continuation is based on keyword matching



                    influencing_factors=[f"Related to task: {active_task.goal}", f"Intent: {intent_type}"],



                    memory_influence={"task_goal": active_task.goal},




                )




                self._decision_trace_collector.record_decision(decision_trace, execution_id=None)  # No trace yet




            else:




                # Not related - clear active task (will create new if needed)




                self._task_manager.clear_active_task()




                logger.info("Request not related to active task, clearing")







                intent_type = intent.intent_type.value if intent else "unknown"





                intent_type = intent.intent_type.value if intent else "unknown"

                # Record task continuation decision trace




                from sokol.runtime.decision_trace import DecisionTrace, DecisionType




                decision_trace = DecisionTrace(




                    trace_id=self._decision_trace_collector.generate_trace_id(),




                    decision_type=DecisionType.TASK_CONTINUATION,



                    input_context={"request": text, "task_id": active_task.task_id, "intent_type": intent_type},



                    options_considered=["continue_task", "create_new_task"],




                    selected_option="create_new_task",




                    confidence_score=0.6,



                    influencing_factors=["Request not related to active task", f"Intent: {intent_type}"],



                    memory_influence={"task_goal": active_task.goal},




                )




                self._decision_trace_collector.record_decision(decision_trace, execution_id=None)  # No trace yet









        # Memory read BEFORE router (personalization context)




        memory_context_obj = self._memory_layer.retrieve_context(text, limit=3)









        # Inject memory context (non-blocking, augments input internally)




        # Sanitize to prevent injection attacks




        memory_context = self._get_memory_context()




        if memory_context:




            # Sanitize: remove control characters and limit length




            import re




            sanitized_context = re.sub(r'[\x00-\x1f]', '', memory_context)




            sanitized_context = sanitized_context[:500]  # Limit length




            # Use metadata field instead of text concatenation when possible




            text = f"{text}\n\n[Memory Context]\n{sanitized_context}"









        # Emit input event




        self._event_bus.create_and_emit(




            EventType.USER_INPUT,




            source,




            {"text": text},




        )









        # Transition to thinking




        self._state_machine.transition(AgentState.THINKING, "user_input")









        # Call input callback if set




        if self._on_input_callback:




            self._on_input_callback(text)









        # STRICT: Ensure state always returns to IDLE/ERROR



        try:



            self._execute_agent_loop(text, source, memory_context_obj, screen_context)



        finally:



            # Safety fallback: force to IDLE if not already there



            if self._state_machine.state not in (AgentState.IDLE, AgentState.ERROR):



                logger.warning_data(



                    "State cleanup in finally block",



                    {"current_state": self._state_machine.state.value},



                )



                self._state_machine.force_transition(AgentState.IDLE, "finally_cleanup")







    def _execute_agent_loop(self, user_input: str, source: str = "user", memory_context_obj: Any = None, screen_context: Optional[dict] = None) -> AgentResponse:



        """



        Strict agent execution loop with clear phases.







        Phases:



        1. Route input through IntentRouter (LLM > rule-based > rejected)



        2. Safety validation for tool calls



        3. Execute tool (if validated)



        4. Build structured response



        5. Emit response



        6. State transition to IDLE







        Args:



            user_input: User input text



            source: Input source (voice/ui/debug) for response mode selection



            memory_context_obj: Memory context object from MemoryLayer



            screen_context: Optional screen context data from ScreenInputAdapter



        """



        try:



            # PHASE 1: Route input through IntentRouter



            proposed_action = self._intent_router.route(user_input)





            if proposed_action is None:
                return self._response_builder.build(final_text="Routing failed.", success=False)




            logger.info_data(




                "Routing decision",




                {"action_type": proposed_action.action_type, "source": proposed_action.source.value},




            )









            # Collect tool results for structured response




            tool_results: list[Any] = []




            final_text: str = ""




            success: bool = True









            # PHASE 0: Start trace collection




            self._trace_collector.start_trace(user_input, source)




            self._trace_collector.start_execution_timer()









            # PHASE 0.5: Pre-execution hardening checks (monitor + warn, not block)




            pre_execution_violations = self._hardening_engine.run_pre_execution_checks()




            if pre_execution_violations:




                # Log violations in trace (non-blocking)




                self._trace_collector.record_hardening_violations(pre_execution_violations)




                logger.warning_data(




                    "Pre-execution hardening violations detected",




                    {"count": len(pre_execution_violations)},




                )









            # PHASE 1: Record router decision




            self._trace_collector.record_router_decision(proposed_action)









            # PHASE 1.5: Control layer evaluation (before execution)




            if proposed_action.action_type == "tool_call":




                control_result = self._control_layer.evaluate(




                    action=proposed_action,




                    context=user_input,




                    tool_metadata=None,  # Could fetch from tool registry if needed




                )









                # Record control layer decision trace




                from sokol.runtime.decision_trace import DecisionTrace, DecisionType




                decision_trace = DecisionTrace(




                    trace_id=self._decision_trace_collector.generate_trace_id(),




                    decision_type=DecisionType.RISK_ASSESSMENT,




                    input_context={"tool": proposed_action.tool, "context": user_input},




                    options_considered=["ALLOW", "REQUIRE_CONFIRMATION", "BLOCKED"],




                    selected_option=control_result.decision.value,




                    confidence_score=0.8,  # Control layer is deterministic




                    influencing_factors=[control_result.explanation],




                )




                self._decision_trace_collector.record_decision(decision_trace, execution_id=self._trace_collector._current_trace.trace_id if self._trace_collector._current_trace else None)









                # Record control decision




                self._trace_collector.record_control_decision(control_result)









                # Handle control decision




                if control_result.decision == ControlDecision.BLOCKED:




                    logger.warning_data(




                        "Action blocked by control layer",




                        {"reason": control_result.explanation},




                    )




                    final_text = f"Action blocked: {control_result.explanation}"




                    success = False




                elif control_result.decision == ControlDecision.REQUIRE_CONFIRMATION:




                    # Store pending action for confirmation




                    self._pending_action = proposed_action




                    self._pending_control_result = control_result









                    # Generate plan for user understanding




                    plan = self._plan_generator.generate_plan(proposed_action, control_result)









                    # Build confirmation request message




                    confirmation_message = f"⚠️ Требуется подтверждение действия\n\n"




                    confirmation_message += f"Действие: {control_result.explanation}\n"




                    confirmation_message += f"Уровень риска: {control_result.risk_level.value}\n"









                    if plan:




                        confirmation_message += f"\n{plan}\n"









                    if control_result.plan_preview:




                        confirmation_message += f"\nТехнический план:\n"




                        for step in control_result.plan_preview:




                            confirmation_message += f"  - {step}\n"









                    confirmation_message += f"\nДля подтверждения напишите: да, подтверждаю, выполняй"




                    confirmation_message += f"\nДля отмены напишите: нет, отмена, стоп"







                    # Return confirmation request as response



                    response = self._response_builder.build(



                        final_text=confirmation_message,



                        tool_results=[],



                        success=False,  # Not executed yet



                        stability_score=1.0,



                        stability_flags=[],



                    )







                    # Format response based on mode (presentation layer)



                    user_bias = memory_context_obj.user_bias if memory_context_obj else None



                    mode = self._response_formatter.select_mode(source, user_bias)



                    state = self._ux_realness.create_state(phase="processing")



                    response = self._response_formatter.format(response, mode, state, context=user_input)



                    self.emit_response(response)



                    self._state_machine.transition(AgentState.IDLE, "awaiting_confirmation")



                    return  # Stop execution loop



                # If ALLOW, continue to execution









            # PHASE 2: Safety validation for tool calls




            if proposed_action.action_type == "tool_call" and success:




                # Detect tool chain (backward compatibility: wrap single tool into chain)




                if proposed_action.tool_chain:




                    # Chain execution




                    chain = proposed_action.tool_chain




                    logger.info_data(




                        "Executing tool chain",




                        {"step_count": chain.step_count},




                    )









                    # Execute steps sequentially with branching support




                    step_index = 0




                    while step_index < len(chain.steps):




                        step = chain.steps[step_index]




                        step_number = step_index + 1









                        logger.info_data(




                            "Executing chain step",




                            {"step": step_number, "total": chain.step_count, "tool": step.tool},




                        )









                        # Create temporary ProposedAction for this step




                        step_action = ProposedAction(




                            source=proposed_action.source,




                            action_type="tool_call",




                            tool=step.tool,




                            args=step.params,




                            text=proposed_action.text,




                            confidence=proposed_action.confidence,




                        )









                        # Safety validation




                        if not self._validate_safety(step_action):




                            logger.warning_data(




                                "Chain step denied by safety layer",




                                {"step": step_number, "tool": step.tool},




                            )




                            final_text = f"Chain stopped at step {step_number}: Action denied by safety layer"




                            success = False




                            break









                        # Tool intelligence (decision support)




                        original_tool = step.tool




                        intent = proposed_action.text or user_input




                        memory_context = self._get_memory_context()









                        # Inject previous step results into context (minimal injection)




                        if step_index > 0 and tool_results:




                            # Add last result to context for next step




                            last_result = tool_results[-1]




                            if hasattr(last_result, "data"):




                                memory_context += f"\nPrevious step result: {str(last_result.data)[:200]}"









                        # Add memory influence to tool intelligence (tool success scores)




                        tool_success_scores = memory_context_obj.tool_memory if memory_context_obj else {}









                        ranked_tools = self._tool_intelligence.rank_tools(




                            tools=[original_tool],




                            intent=intent,




                            context=memory_context,




                            stability_score=0.0,




                            tool_success_scores=tool_success_scores,




                        )









                        selected_tool = self._tool_intelligence.select_best_tool(




                            ranked_tools,




                            fallback_tool=original_tool,




                        )









                        # Record tool selection decision trace




                        from sokol.runtime.decision_trace import DecisionTrace, DecisionType




                        decision_trace = DecisionTrace(




                            trace_id=self._decision_trace_collector.generate_trace_id(),




                            decision_type=DecisionType.TOOL_SELECTION,




                            input_context={"intent": intent, "step": step_number, "chain": True},




                            options_considered=[t.tool for t in ranked_tools],




                            selected_option=selected_tool,




                            confidence_score=ranked_tools[0].score if ranked_tools else 0.0,




                            influencing_factors=[reason for score in ranked_tools for reason in score.reasons],




                            tool_history_influence=tool_success_scores if tool_success_scores else None,




                        )




                        self._decision_trace_collector.record_decision(decision_trace, execution_id=self._trace_collector._current_trace.trace_id if self._trace_collector._current_trace else None)









                        # Update tool name if intelligence engine selected different one




                        if selected_tool != original_tool:




                            logger.info_data(




                                "Tool intelligence changed tool selection in chain",




                                {"step": step_number, "original": original_tool, "selected": selected_tool},




                            )




                            step_action.tool = selected_tool









                        # Execute tool with recovery




                        def execute_with_recovery(tool_name: str, params: dict[str, Any]) -> Any:




                            """Execute tool through registry with contract normalization."""




                            # Normalize input before execution




                            active_task = self._task_manager.get_active_task()




                            task_id = active_task.task_id if active_task else None









                            # Get trace ID from trace collector if available




                            trace_id = ""




                            if self._trace_collector._current_trace:




                                trace_id = self._trace_collector._current_trace.trace_id









                            # Normalize input




                            input_contract = self._tool_contract_normalizer.normalize_input(




                                tool_id=tool_name,




                                input_data=params,




                                context={"source": source},




                                risk_level="low",




                                task_id=task_id,




                                trace_id=trace_id,




                            )









                            # Execute with normalized input




                            raw_result = self._tool_registry.execute(tool_name, **input_contract.input)









                            # Normalize output after execution




                            output_contract = self._tool_contract_normalizer.normalize_output(




                                tool_id=tool_name,




                                raw_result=raw_result,




                                execution_time_ms=0.0,  # Would track actual time




                                retry_count=0,




                            )









                            return output_contract









                        tool_result, recovery_info = self._failure_recovery.execute_with_recovery(




                            tool_name=selected_tool,




                            params=step.params,




                            execute_func=execute_with_recovery,




                            tool_intelligence_engine=self._tool_intelligence,




                            intent=proposed_action.text or user_input,




                            context=memory_context,




                            stability_score=0.0,




                        )




                        tool_results.append(tool_result)









                        # Record tool call and result for trace




                        self._trace_collector.record_tool_call(selected_tool, step.params)




                        self._trace_collector.record_tool_result(selected_tool, tool_result)









                        # Record recovery info in tool result




                        if hasattr(tool_result, "__dict__"):




                            tool_result.__dict__["recovery_info"] = recovery_info









                        # Record recovery info in trace




                        self._trace_collector.record_recovery_attempt(




                            original_tool=selected_tool,




                            final_tool=recovery_info["final_tool"],




                            retry_count=recovery_info["retry_count"],




                            fallback_used=recovery_info["fallback_used"],




                            success=getattr(tool_result, "success", True),




                        )









                        # Record tool result for future intelligence




                        tool_success = tool_result.success if hasattr(tool_result, "success") else True




                        self._tool_intelligence.record_tool_result(selected_tool, tool_success)









                        # Check for failure - stop chain immediately (unless condition handles it)




                        if not tool_success:




                            logger.warning_data(




                                "Chain step failed, stopping chain",




                                {"step": step_number, "tool": selected_tool},




                            )




                            # Use graceful degradation message




                            failure_message = self._failure_recovery.format_failure_message(




                                selected_tool,




                                recovery_info,




                            )




                            final_text = f"Chain stopped at step {step_number}: {failure_message}"




                            success = False




                            break









                        # Update final text with last step result




                        final_text = self._format_tool_result(tool_result)









                        # Evaluate condition for branching (if present)




                        if step.condition:




                            condition_met, reason = self._condition_evaluator.evaluate(




                                step.condition,




                                tool_result,




                            )




                            logger.info_data(




                                "Condition evaluated",




                                {"step": step_number, "met": condition_met, "reason": reason},




                            )









                            if condition_met and step.next_step_override is not None:




                                # Branch to override step




                                next_step = step.next_step_override




                                if 0 <= next_step < len(chain.steps):




                                    logger.info_data(




                                        "Branching to override step",




                                        {"current": step_number, "next": next_step + 1},




                                    )




                                    step_index = next_step




                                    continue




                                else:




                                    logger.warning_data(




                                        "Invalid next_step_override, stopping chain",




                                        {"override": next_step, "max": len(chain.steps)},




                                    )




                                    break




                            elif not condition_met:




                                # Condition not met - stop chain




                                logger.info_data(




                                    "Condition not met, stopping chain",




                                    {"step": step_number, "reason": reason},




                                )




                                break









                        # Move to next step




                        step_index += 1









                    # If chain completed successfully




                    if success:




                        logger.info_data(




                            "Tool chain completed successfully",




                            {"total_steps": len(tool_results)},




                        )









                else:




                    # Single tool execution (backward compatibility)




                    if not self._validate_safety(proposed_action):




                        final_text = "Action denied by safety layer"




                        success = False




                    else:




                        # PHASE 2.5: Tool intelligence (decision support before execution)




                        original_tool = proposed_action.tool




                        tool_intent = proposed_action.text or user_input  # Use different variable name to avoid conflict




                        memory_context = self._get_memory_context()









                        # Rank and select tool (non-blocking, decision support only)




                        # Add memory influence to tool intelligence (tool success scores)




                        tool_success_scores = memory_context_obj.tool_memory if memory_context_obj else {}









                        # Pass extracted intent context to tool intelligence (for better scoring, NOT for decisions)




                        # Use the intent extracted at process_input level




                        intent_context = f"{intent.intent_type.value}: {intent.primary_goal}" if intent else ""









                        ranked_tools = self._tool_intelligence.rank_tools(




                            tools=[original_tool],




                            intent=intent_context,




                            context=memory_context,




                            stability_score=0.0,  # Will be updated after stability check




                            tool_success_scores=tool_success_scores,




                        )









                        selected_tool = self._tool_intelligence.select_best_tool(




                            ranked_tools,




                            fallback_tool=original_tool,




                        )









                        # Record tool selection decision trace




                        from sokol.runtime.decision_trace import DecisionTrace, DecisionType




                        decision_trace = DecisionTrace(




                            trace_id=self._decision_trace_collector.generate_trace_id(),




                            decision_type=DecisionType.TOOL_SELECTION,




                            input_context={"intent": intent_context},




                            options_considered=[t.tool for t in ranked_tools],




                            selected_option=selected_tool,




                            confidence_score=ranked_tools[0].score if ranked_tools else 0.0,




                            influencing_factors=[reason for score in ranked_tools for reason in score.reasons],




                            tool_history_influence=tool_success_scores if tool_success_scores else None,




                        )




                        self._decision_trace_collector.record_decision(decision_trace, execution_id=self._trace_collector._current_trace.trace_id if self._trace_collector._current_trace else None)









                        # Update tool name if intelligence engine selected different one




                        if selected_tool != original_tool:




                            logger.info_data(




                                "Tool intelligence changed tool selection",




                                {"original": original_tool, "selected": selected_tool},




                            )




                            proposed_action.tool = selected_tool









                        # PHASE 3: Execute tool with recovery




                        def execute_with_recovery(tool_name: str, params: dict[str, Any]) -> Any:




                            """Execute tool through registry with contract normalization."""




                            # Normalize input before execution




                            active_task = self._task_manager.get_active_task()




                            task_id = active_task.task_id if active_task else None









                            # Get trace ID from trace collector if available




                            trace_id = ""




                            if self._trace_collector._current_trace:




                                trace_id = self._trace_collector._current_trace.trace_id









                            # Normalize input




                            input_contract = self._tool_contract_normalizer.normalize_input(




                                tool_id=tool_name,




                                input_data=params,




                                context={"source": source},




                                risk_level="low",




                                task_id=task_id,




                                trace_id=trace_id,




                            )









                            # Execute with normalized input




                            raw_result = self._tool_registry.execute(tool_name, **input_contract.input)









                            # Normalize output after execution




                            output_contract = self._tool_contract_normalizer.normalize_output(




                                tool_id=tool_name,




                                raw_result=raw_result,




                                execution_time_ms=0.0,  # Would track actual time




                                retry_count=0,




                            )









                            return output_contract









                        tool_result, recovery_info = self._failure_recovery.execute_with_recovery(




                            tool_name=selected_tool,




                            params=proposed_action.args or {},




                            execute_func=execute_with_recovery,




                            tool_intelligence_engine=self._tool_intelligence,




                            intent=tool_intent,




                            context=memory_context,




                            stability_score=0.0,




                        )




                        tool_results.append(tool_result)









                        # Record tool call and result for trace




                        self._trace_collector.record_tool_call(selected_tool, proposed_action.args or {})




                        self._trace_collector.record_tool_result(selected_tool, tool_result)









                        # Record recovery info in tool result




                        if hasattr(tool_result, "__dict__"):




                            tool_result.__dict__["recovery_info"] = recovery_info









                        # Record recovery info in trace




                        self._trace_collector.record_recovery_attempt(




                            original_tool=selected_tool,




                            final_tool=recovery_info["final_tool"],




                            retry_count=recovery_info["retry_count"],




                            fallback_used=recovery_info["fallback_used"],




                            success=getattr(tool_result, "success", True),




                        )









                        # Record tool result for future intelligence




                        tool_success = tool_result.success if hasattr(tool_result, "success") else True




                        self._tool_intelligence.record_tool_result(selected_tool, tool_success)









                        # Generate final response text




                        if tool_success:




                            final_text = self._format_tool_result(tool_result)




                        else:




                            # Use graceful degradation message




                            failure_message = self._failure_recovery.format_failure_message(




                                selected_tool,




                                recovery_info,




                            )




                            final_text = failure_message




                        success = tool_success




            else:




                # Direct response (final_answer or clarification)




                final_text = proposed_action.text or "No response"









            # PHASE 3.5: Stability check (observational, non-blocking)




            stability_report = self._stability_checker.evaluate(




                tool_results=tool_results,




                router_output=proposed_action,




            )









            # Record stability report for trace




            self._trace_collector.record_stability_report(stability_report)









            # PHASE 3.6: Post-execution hardening checks (monitor + warn, not block)




            post_execution_violations = self._hardening_engine.run_post_execution_checks(




                tool_results=tool_results,




                stability_score=stability_report.stability_score,




            )




            if post_execution_violations:




                # Log violations in trace (non-blocking)




                self._trace_collector.record_hardening_violations(post_execution_violations)




                logger.warning_data(




                    "Post-execution hardening violations detected",




                    {"count": len(post_execution_violations)},




                )









            # Apply recovery penalty to stability score




            total_recovery_penalty = 0.0




            for result in tool_results:




                if hasattr(result, "__dict__") and "recovery_info" in result.__dict__:




                    recovery_info = result.__dict__["recovery_info"]




                    penalty = self._failure_recovery.get_stability_penalty(recovery_info)




                    total_recovery_penalty += penalty









            if total_recovery_penalty > 0:




                stability_report.stability_score = max(0.0, stability_report.stability_score - total_recovery_penalty)




                logger.info_data(




                    "Applied recovery penalty to stability score",




                    {"penalty": total_recovery_penalty, "new_score": stability_report.stability_score},




                )









            # Record stability report for trace




            self._trace_collector.record_stability_report(stability_report)









            # Record memory context for trace




            memory_context = self._get_memory_context()




            self._trace_collector.record_memory_context(memory_context)









            # Record memory influence in trace




            if memory_context_obj:




                self._trace_collector.record_memory_influence({




                    "user_bias": memory_context_obj.user_bias,




                    "tool_memory": memory_context_obj.tool_memory,




                    "relevant_interactions_count": len(memory_context_obj.relevant_interactions),




                    "summary": memory_context_obj.summary,




                })









            # PHASE 4: Build structured response




            # Generate plan for user understanding (for chains or medium/high risk)




            plan = ""




            if proposed_action.action_type == "tool_call":




                # Add memory influence to plan verbosity




                verbosity_boost = 1.0




                if memory_context_obj and "verbosity_boost" in memory_context_obj.user_bias:




                    verbosity_boost = memory_context_obj.user_bias["verbosity_boost"]




                plan = self._plan_generator.generate_plan(proposed_action, None, verbosity_boost=verbosity_boost)









            # Prepend plan to response if it exists




            if plan:




                final_text = f"{plan}\n\n{final_text}"









            response = self._response_builder.build(




                final_text=final_text,




                tool_results=tool_results,




                success=success,




                stability_score=stability_report.stability_score,




                stability_flags=stability_report.stability_flags,




            )









            # Format response based on mode (presentation layer)




            user_bias = memory_context_obj.user_bias if memory_context_obj else None




            mode = self._response_formatter.select_mode(source, user_bias)









            # Record response mode selection decision trace




            from sokol.runtime.decision_trace import DecisionTrace, DecisionType




            decision_trace = DecisionTrace(




                trace_id=self._decision_trace_collector.generate_trace_id(),




                decision_type=DecisionType.RESPONSE_MODE_SELECTION,




                input_context={"source": source, "user_bias": str(user_bias)},




                options_considered=["COMPACT", "STANDARD", "DETAILED"],




                selected_option=mode.value,




                confidence_score=0.9,  # Mode selection is deterministic based on source




                influencing_factors=[f"Source: {source}", f"User bias: {user_bias}"],




                memory_influence={"user_bias": user_bias} if user_bias else None,




            )




            self._decision_trace_collector.record_decision(decision_trace, execution_id=self._trace_collector._current_trace.trace_id if self._trace_collector._current_trace else None)









            # Create execution state for UX realness




            # Add progress info for chains




            if proposed_action.tool_chain and success:




                chain = proposed_action.tool_chain




                state = self._ux_realness.create_state(




                    phase="finalizing",




                    step=len(tool_results),




                    total_steps=chain.step_count,




                    context=user_input,




                )




            else:




                state = self._ux_realness.create_state(




                    phase="finalizing",




                    context=user_input,




                )









            # Add memory context for continuity




            memory_context_for_ux = memory_context_obj.summary if memory_context_obj else ""









            response = self._response_formatter.format(response, mode, state, context=memory_context_for_ux)









            # PHASE 4.5: Persist memory events (non-blocking)




            self._persist_memory_events(response.memory_events)









            # PHASE 5: Emit structured response




            self.emit_response(response)









            # Memory write AFTER response (update user model and memory)




            # Extract tool info from execution




            tool_used = None




            tool_success = True




            risk_level = None









            if tool_results:




                # Get the last tool used




                if hasattr(tool_results[-1], "__dict__"):




                    tool_used = tool_results[-1].__dict__.get("recovery_info", {}).get("final_tool")




                    if not tool_used:




                        tool_used = proposed_action.tool if proposed_action.action_type == "tool_call" else None




                    tool_success = getattr(tool_results[-1], "success", True)









            # Store interaction in memory with multimodal data




            voice_confidence = None




            if source == "voice":




                # Extract voice confidence if available (would come from UnifiedInputContext)




                voice_confidence = 0.0  # Placeholder - would be passed from context









            self._memory_layer.store_interaction(




                source=source,




                input_text=user_input,




                response_text=final_text,




                tool_used=tool_used,




                tool_success=tool_success,




                risk_level=risk_level,




                mode=mode.value,




                voice_confidence=voice_confidence,




                screen_context=screen_context,




                tool_decision={"tool": tool_used, "risk": risk_level} if tool_used else None,




            )









            # Task Layer: Complete or update task status




            active_task = self._task_manager.get_active_task()




            if active_task and success:




                # If execution was successful, task may be complete




                # For now, we'll complete tasks that have no steps (single-shot tasks)




                if not active_task.steps:




                    self._task_manager.complete_task(active_task.task_id)




                    logger.info_data(




                        "Task completed",




                        {"task_id": active_task.task_id},




                    )




                elif active_task.current_step < len(active_task.steps):




                    # Update current step




                    self._task_manager.update_task_status(




                        active_task.task_id,




                        active_task.status,




                        current_step=active_task.current_step + 1,




                    )




            elif active_task and not success:




                # Task failed




                self._task_manager.fail_task(active_task.task_id, reason="Execution failed")




                logger.warning_data(




                    "Task failed",




                    {"task_id": active_task.task_id},




                )









            # PHASE 5.5: Finalize and log trace




            # Get decision traces for this execution




            execution_id = self._trace_collector._current_trace.trace_id if self._trace_collector._current_trace else None




            decision_traces = []




            if execution_id:




                decision_traces_dicts = []




                for dt in self._decision_trace_collector.get_execution_trace_chain(execution_id):




                    decision_traces_dicts.append({




                        "trace_id": dt.trace_id,




                        "decision_type": dt.decision_type.value,




                        "selected_option": dt.selected_option,




                        "confidence_score": dt.confidence_score,




                        "influencing_factors": dt.influencing_factors,




                        "timestamp": dt.timestamp,




                    })




                self._trace_collector.record_decision_traces(decision_traces_dicts)









            trace = self._trace_collector.finalize_trace(




                response=final_text,




                success=success,




                error="" if success else "Execution failed",




            )




            if trace:




                self._trace_collector.log_trace(trace)









            # PHASE 6: Transition to IDLE



            self._state_machine.transition(AgentState.IDLE, "agent_loop_complete")

            return response






        except Exception as e:



            logger.error_data("Agent loop failed", {"error": str(e)})



            import traceback
            error_msg = f"Error: {str(e)}"
            error_response = self._response_builder.build(



                final_text=f"Error: {str(e)}",



                success=False,



            )



            # Format error response based on mode (presentation layer)



            user_bias = memory_context_obj.user_bias if memory_context_obj else None



            mode = self._response_formatter.select_mode(source, user_bias)



            state = self._ux_realness.create_state(phase="finalizing", context=user_input)



            error_response = self._response_formatter.format(error_response, mode, state, context=user_input)



            self.emit_response(error_response)



            self._state_machine.transition(AgentState.ERROR, "agent_loop_error")

            return error_response








    def _validate_safety(self, action: ProposedAction) -> bool:




        """




        Validate proposed action through safety layer.









        Returns True if action is safe to execute.




        """




        from sokol.safety.risk import RiskAssessor, assess_tool_risk




        from sokol.safety.confirm import ConfirmationTimeout




        from sokol.core.types import RiskLevel









        if not action.tool:




            return True  # Text responses are always safe









        # Assess risk




        risk_level = assess_tool_risk(action.tool, action.args or {})









        # If dangerous, require confirmation




        if risk_level == RiskLevel.DANGEROUS:




            logger.warning_data(




                "Dangerous action requires confirmation",




                {"tool": action.tool, "risk": risk_level.value},




            )









            # Create confirmation request




            request = self._confirmation_manager.create_request(




                tool_name=action.tool,




                action_description=f"Execute {action.tool}",




                risk_level=risk_level,




                parameters=action.args or {},




                consequences="This action could modify system state or delete data",




                timeout=self._config.safety.confirmation_timeout,




            )









            # Emit confirmation request event for UI




            self._event_bus.create_and_emit(




                EventType.CONFIRM_REQUEST,




                "orchestrator",




                {"request_id": request.id, "tool": action.tool, "args": action.args},




            )









            # Use callback if available (UI integration)




            if self._on_confirm_callback:




                approved = self._on_confirm_callback(request)




                self._confirmation_manager.respond(request.id, approved=approved)




            else:




                # Default: wait for response with timeout




                try:




                    response = self._confirmation_manager.wait_for_response(




                        request.id,




                        timeout=self._config.safety.confirmation_timeout,




                    )




                    approved = response.approved




                except ConfirmationTimeout:




                    logger.warning_data(




                        "Confirmation request timed out",




                        {"request_id": request.id},




                    )




                    self._confirmation_manager.cancel(request.id)




                    approved = False









            if not approved:




                logger.warning_data(




                    "Dangerous action denied by user",




                    {"tool": action.tool},




                )




                return False









            logger.info_data(




                "Dangerous action approved by user",




                {"tool": action.tool},




            )









        return True









    def _execute_tool_action(self, action: ProposedAction) -> dict[str, Any]:




        """




        Execute tool action with state transition.









        Returns tool result dict.




        """




        tool_name = action.tool




        args = action.args or {}









        logger.info_data(




            "Executing tool",




            {"tool": tool_name, "source": action.source.value, "args": str(args)[:100]},




        )









        # Transition to EXECUTING




        self._state_machine.transition(AgentState.EXECUTING, f"tool:{tool_name}")









        try:




            result = self._tool_registry.execute(tool_name, args)









            return {




                "success": result.success,




                "data": result.data if result.success else None,




                "error": result.error if not result.success else None,




            }




        except Exception as e:




            logger.error_data("Tool execution error", {"error": str(e)})




            return {




                "success": False,




                "error": str(e),




            }









    def _format_tool_result(self, result: dict[str, Any]) -> str:




        """Format tool result for user."""




        if result["success"]:




            data = result.get("data")




            if isinstance(data, dict):




                return f"Success: {data}"




            return f"Success: {data}"




        else:




            return f"Failed: {result.get('error', 'Unknown error')}"









    def emit_response(self, response: str | AgentResponse, source: str = "agent") -> None:




        """Emit a response to the user."""




        # Handle both string and AgentResponse for backward compatibility




        if isinstance(response, AgentResponse):




            text = response.user_text




            logger.info_data(




                "Emitting structured response",




                {"source": source, "text": text[:100], "success": response.success},




            )




        else:




            text = response




            logger.info_data(




                "Emitting response",




                {"source": source, "text": text[:100]},




            )









        # Call response callback with user text




        if self._on_response_callback:




            self._on_response_callback(text)









    def request_confirmation(self, request: Any) -> bool:




        """Request user confirmation for dangerous action."""




        self._state_machine.transition(




            AgentState.WAITING_CONFIRM,




            f"tool:{request.tool_name}",




        )









        self._event_bus.create_and_emit(




            EventType.CONFIRM_REQUEST,




            "orchestrator",




            {"request": request.model_dump() if hasattr(request, "model_dump") else str(request)},




        )









        # Call confirm callback if set




        if self._on_confirm_callback:




            return self._on_confirm_callback(request)









        # Default: deny dangerous actions without callback




        return False









    def set_response_callback(self, callback: Callable[[str], None]) -> None:




        """Set callback for agent responses."""




        self._on_response_callback = callback









    def set_confirm_callback(self, callback: Callable[[Any], bool]) -> None:




        """Set callback for confirmation requests."""




        self._on_confirm_callback = callback









    def set_preprocess_callback(self, callback: Callable[[str], str] | None) -> None:




        """Set preprocessing callback for input normalization."""




        self._preprocess_callback = callback









    def set_memory_manager(self, memory_manager: Any) -> None:




        """Set memory manager reference for context injection and event persistence."""




        self._memory_manager = memory_manager




        logger.info("Memory manager set in orchestrator")









    def trigger_emergency_stop(self, reason: str = "") -> None:




        """




        Trigger emergency stop via control layer.









        Args:




            reason: Reason for emergency stop




        """




        self._control_layer.trigger_emergency_stop(reason)




        # Clear pending action on emergency stop




        self._pending_action = None




        self._pending_control_result = None




        logger.warning_data("Emergency stop triggered via orchestrator", {"reason": reason})









    def clear_emergency_stop(self) -> None:




        """Clear emergency stop flag via control layer."""




        self._control_layer.clear_emergency_stop()




        logger.info("Emergency stop cleared via orchestrator")









    def is_emergency_stop_active(self) -> bool:




        """Check if emergency stop is active via control layer."""




        return self._control_layer.is_emergency_stop_active()









    def _execute_pending_action(self) -> None:




        """Execute pending action after user confirmation."""




        if self._pending_action is None:




            logger.warning("No pending action to execute")




            return









        # Re-check emergency stop before execution (safety)




        if self._is_emergency_triggered():




            logger.warning("Emergency stop active, cancelling pending action")




            self._pending_action = None




            self._pending_control_result = None




            return



        



        

        logger.info("Executing confirmed pending action")









        # Clear pending action (we're executing it now)




        action = self._pending_action




        source = action.source.value if action.source else "user"




        self._pending_action = None




        self._pending_control_result = None









        # Execute the action through the normal pipeline




        # Note: Control layer bypassed since user already confirmed,




        # but emergency stop check is still performed above




        self._execute_agent_loop(action.text or "", source)









    def _persist_memory_events(self, memory_events: list[dict]) -> bool:




        """




        Persist memory events to memory manager (non-blocking).









        Args:




            memory_events: List of memory event dictionaries from AgentResponse




        """





        # Sanitize and persist each event




        for event_dict in memory_events:




            try:




                # Create MemoryEvent from dict




                event = MemoryEvent(




                    event_type=event_dict.get("event_type", "fact"),




                    data=event_dict.get("data", {}),




                    timestamp=event_dict.get("timestamp"),




                )









                # Sanitize event




                sanitized = self._memory_sanitizer.sanitize(event)




                if sanitized is None:




                    logger.debug_data(




                        "Memory event blocked by sanitizer",




                        {"event_type": event.event_type},




                    )




                    continue









                # Persist to appropriate memory store based on event type




                if sanitized.event_type == "user_preference":




                    self._memory_manager.set_preference(




                        sanitized.data.get("key"),




                        sanitized.data.get("value"),




                    )




                elif sanitized.event_type == "tool_result":




                    # Store as pattern in long-term memory




                    self._memory_manager.save_pattern(




                        "tool_result",




                        sanitized.data,




                        tags=[sanitized.event_type],




                    )




                elif sanitized.event_type == "fact":




                    # Store as context in session




                    self._memory_manager.set_context(




                        f"fact_{len(memory_events)}",




                        sanitized.data,




                    )




                elif sanitized.event_type == "state_marker":




                    # Store as context in session




                    self._memory_manager.set_context(




                        f"state_{sanitized.data.get('key', 'unknown')}",




                        sanitized.data,




                    )









                logger.debug_data(




                    "Memory event persisted",




                    {"event_type": sanitized.event_type},




                )









            except Exception as e:




                # Memory write failure should not block execution



                logger.warning_data(
                    "Failed to persist memory event",
                    {"error": str(e)},
                )

        return True





    def _get_memory_context(self) -> str:




        """




        Get memory context for injection into LLM/router input.









        Returns:




            Context string (empty if no memory manager or no context)




        """




        if not self._memory_manager:




            return ""









        try:




            # Get recent conversation history




            conversation = self._memory_manager.get_conversation_history(limit=10)









            # Get session context




            context_dict = {}




            if self._memory_manager.current_session:




                context_dict = self._memory_manager.current_session.context or {}









            # Get user preferences




            preferences = {}




            if self._memory_manager.current_profile:




                preferences = self._memory_manager.current_profile.preferences or {}









            # Build context string (minimal, non-blocking)




            context_parts = []









            if conversation:




                context_parts.append("Recent conversation:")




                for msg in conversation[-5:]:  # Last 5 messages




                    context_parts.append(f"  {msg['role']}: {msg['content'][:50]}")









            if context_dict:




                context_parts.append("Session context:")




                for key, value in list(context_dict.items())[:3]:  # Top 3 context items




                    context_parts.append(f"  {key}: {str(value)[:50]}")









            if preferences:




                context_parts.append("User preferences:")




                for key, value in list(preferences.items())[:3]:  # Top 3 preferences




                    context_parts.append(f"  {key}: {str(value)[:50]}")









            return "\n".join(context_parts)









        except Exception as e:




            # Memory read failure should not block execution




            logger.warning_data(




                "Failed to get memory context",




                {"error": str(e)},




            )




            return ""









    def set_callbacks(




        self,




        on_input: Callable[[str], None] | None = None,




        on_response: Callable[[str], None] | None = None,




        on_confirm: Callable[[Any], bool] | None = None,




        on_preprocess: Callable[[str], str] | None = None,




    ) -> None:




        """Set callbacks for UI integration."""




        self._on_input_callback = on_input




        self._on_response_callback = on_response




        self._on_confirm_callback = on_confirm




        self._preprocess_callback = on_preprocess









    def _on_state_change(self, event: AgentEvent) -> None:




        """Handle state change events."""




        with self._lock:




            # Update state enter time for watchdog




            self._state_enter_time = time.time()









        logger.debug_data(




            "State change event",




            event.data,




        )









    def _handle_emergency_stop(self, event: AgentEvent) -> None:




        """Handle emergency stop event from any source."""




        self.emergency_stop(event.data.get("reason", "event"))









    def _setup_signal_handlers(self) -> None:




        """Setup signal handlers for graceful shutdown."""




        def signal_handler(signum: int, frame: Any) -> None:




            logger.info_data("Signal received", {"signal": signum})




            self.stop(f"signal_{signum}")









        # Only works in main thread




        try:




            signal.signal(signal.SIGINT, signal_handler)




            signal.signal(signal.SIGTERM, signal_handler)




        except ValueError:




            # Not in main thread




            pass









    def run_forever(self) -> None:




        """Run the main loop (blocking)."""




        self.start()




        try:




            self._shutdown_event.wait()




        except KeyboardInterrupt:




            self.stop("keyboard_interrupt")









    async def run_async(self) -> None:




        """Run the main loop (async)."""




        self._main_loop = asyncio.get_running_loop()




        self.start()









        try:




            while self._running:




                await asyncio.sleep(0.1)




        except asyncio.CancelledError:




            self.stop("async_cancel")









    def __repr__(self) -> str:




        return f"Orchestrator(state={self.state.value}, running={self._running})"





# -*- coding: utf-8 -*-
"""
SOKOL v8.0 - Code Assistant Agent
Advanced AI programming assistant with code generation, analysis, and optimization
"""
import os
import re
import ast
import json
import subprocess
import tempfile
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .core import OllamaClient
from .config import OLLAMA_MODEL, OLLAMA_API_BASE

logger = logging.getLogger("sokol.code_assistant")


@dataclass
class CodeAnalysis:
    """Code analysis results"""
    language: str
    complexity: str
    issues: List[str]
    suggestions: List[str]
    optimizations: List[str]
    security_issues: List[str]
    performance_score: float


@dataclass
class CodeGeneration:
    """Code generation results"""
    code: str
    language: str
    explanation: str
    dependencies: List[str]
    usage_example: str
    quality_score: float


class CodeParser:
    """Parse and analyze code structure"""
    
    def __init__(self):
        self.supported_languages = {
            'python': self._parse_python,
            'javascript': self._parse_javascript,
            'typescript': self._parse_typescript,
            'java': self._parse_java,
            'cpp': self._parse_cpp,
            'csharp': self._parse_csharp,
            'html': self._parse_html,
            'css': self._parse_css,
            'json': self._parse_json,
            'sql': self._parse_sql
        }
    
    def detect_language(self, code: str) -> str:
        """Detect programming language from code"""
        code_lower = code.lower().strip()
        
        # Check for specific patterns
        if code_lower.startswith(('<html', '<!doctype', '<?xml')):
            return 'html'
        elif code_lower.startswith(('def ', 'import ', 'from ', 'class ', '#!/usr/bin/python')):
            return 'python'
        elif code_lower.startswith(('function', 'const ', 'let ', 'var ')) or '=>' in code:
            return 'javascript'
        elif 'public class' in code_lower or 'import java.' in code_lower:
            return 'java'
        elif '#include' in code_lower or 'using namespace' in code_lower:
            return 'cpp'
        elif 'using System' in code_lower or 'namespace ' in code_lower:
            return 'csharp'
        elif code_lower.startswith(('{', '[', '"')):
            try:
                json.loads(code)
                return 'json'
            except:
                pass
        elif any(keyword in code_lower for keyword in ['select', 'from', 'where', 'insert', 'update', 'delete']):
            return 'sql'
        elif code_lower.startswith(('.', '#', 'body', 'html')):
            return 'css'
        
        # Default to python if no clear indicators
        return 'python'
    
    def parse_code(self, code: str, language: Optional[str] = None) -> Dict[str, Any]:
        """Parse code and extract structure"""
        if not language:
            language = self.detect_language(code)
        
        parser_func = self.supported_languages.get(language, self._parse_generic)
        return parser_func(code)
    
    def _parse_python(self, code: str) -> Dict[str, Any]:
        """Parse Python code"""
        try:
            tree = ast.parse(code)
            
            functions = []
            classes = []
            imports = []
            variables = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'docstring': ast.get_docstring(node)
                    })
                elif isinstance(node, ast.ClassDef):
                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods.append(item.name)
                    classes.append({
                        'name': node.name,
                        'line': node.lineno,
                        'methods': methods,
                        'docstring': ast.get_docstring(node)
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            variables.append(target.id)
            
            return {
                'language': 'python',
                'functions': functions,
                'classes': classes,
                'imports': imports,
                'variables': variables,
                'lines': len(code.splitlines()),
                'complexity': self._calculate_complexity(tree)
            }
            
        except SyntaxError as e:
            return {
                'language': 'python',
                'error': str(e),
                'lines': len(code.splitlines())
            }
    
    def _parse_javascript(self, code: str) -> Dict[str, Any]:
        """Parse JavaScript code"""
        functions = re.findall(r'(?:function\s+(\w+)|(\w+)\s*=\s*(?:function|\([^)]*\)\s*=>))', code)
        classes = re.findall(r'class\s+(\w+)', code)
        imports = re.findall(r'import.*from\s+[\'"]([^\'"]+)[\'"]', code)
        variables = re.findall(r'(?:const|let|var)\s+(\w+)\s*=', code)
        
        return {
            'language': 'javascript',
            'functions': [{'name': name or func, 'line': 0} for name, func in functions if name or func],
            'classes': [{'name': cls, 'line': 0} for cls in classes],
            'imports': imports,
            'variables': variables,
            'lines': len(code.splitlines()),
            'complexity': len(functions) + len(classes)
        }
    
    def _parse_typescript(self, code: str) -> Dict[str, Any]:
        """Parse TypeScript code"""
        # Similar to JavaScript but with type annotations
        result = self._parse_javascript(code)
        result['language'] = 'typescript'
        
        # Add TypeScript specific features
        interfaces = re.findall(r'interface\s+(\w+)', code)
        types = re.findall(r'type\s+(\w+)\s*=', code)
        
        result['interfaces'] = interfaces
        result['types'] = types
        
        return result
    
    def _parse_java(self, code: str) -> Dict[str, Any]:
        """Parse Java code"""
        classes = re.findall(r'(?:public\s+)?class\s+(\w+)', code)
        methods = re.findall(r'(?:public|private|protected)?(?:\s+static)?\s+\w+\s+(\w+)\s*\(', code)
        imports = re.findall(r'import\s+([^;]+);', code)
        packages = re.findall(r'package\s+([^;]+);', code)
        
        return {
            'language': 'java',
            'classes': [{'name': cls, 'line': 0} for cls in classes],
            'methods': [{'name': method, 'line': 0} for method in methods],
            'imports': imports,
            'packages': packages,
            'lines': len(code.splitlines()),
            'complexity': len(methods) + len(classes)
        }
    
    def _parse_cpp(self, code: str) -> Dict[str, Any]:
        """Parse C++ code"""
        functions = re.findall(r'\w+\s+(\w+)\s*\([^)]*\)\s*{', code)
        classes = re.findall(r'class\s+(\w+)', code)
        includes = re.findall(r'#include\s*[<"]([^>"]+)[>"]', code)
        
        return {
            'language': 'cpp',
            'functions': [{'name': func, 'line': 0} for func in functions],
            'classes': [{'name': cls, 'line': 0} for cls in classes],
            'includes': includes,
            'lines': len(code.splitlines()),
            'complexity': len(functions) + len(classes)
        }
    
    def _parse_csharp(self, code: str) -> Dict[str, Any]:
        """Parse C# code"""
        classes = re.findall(r'(?:public\s+)?class\s+(\w+)', code)
        methods = re.findall(r'(?:public|private|protected)?(?:\s+static)?\s+\w+\s+(\w+)\s*\(', code)
        imports = re.findall(r'using\s+([^;]+);', code)
        namespaces = re.findall(r'namespace\s+([^;]+)', code)
        
        return {
            'language': 'csharp',
            'classes': [{'name': cls, 'line': 0} for cls in classes],
            'methods': [{'name': method, 'line': 0} for method in methods],
            'imports': imports,
            'namespaces': namespaces,
            'lines': len(code.splitlines()),
            'complexity': len(methods) + len(classes)
        }
    
    def _parse_html(self, code: str) -> Dict[str, Any]:
        """Parse HTML code"""
        tags = re.findall(r'<(\w+)', code)
        ids = re.findall(r'id\s*=\s*[\'"]([^\'"]+)[\'"]', code)
        classes = re.findall(r'class\s*=\s*[\'"]([^\'"]+)[\'"]', code)
        
        return {
            'language': 'html',
            'tags': tags,
            'ids': ids,
            'classes': classes,
            'lines': len(code.splitlines()),
            'complexity': len(tags)
        }
    
    def _parse_css(self, code: str) -> Dict[str, Any]:
        """Parse CSS code"""
        selectors = re.findall(r'([^{]+)\s*{', code)
        properties = re.findall(r'(\w+):\s*([^;]+);', code)
        
        return {
            'language': 'css',
            'selectors': [s.strip() for s in selectors],
            'properties': properties,
            'lines': len(code.splitlines()),
            'complexity': len(selectors)
        }
    
    def _parse_json(self, code: str) -> Dict[str, Any]:
        """Parse JSON code"""
        try:
            data = json.loads(code)
            return {
                'language': 'json',
                'structure': self._analyze_json_structure(data),
                'lines': len(code.splitlines()),
                'complexity': len(str(data).split(','))
            }
        except json.JSONDecodeError as e:
            return {
                'language': 'json',
                'error': str(e),
                'lines': len(code.splitlines())
            }
    
    def _parse_sql(self, code: str) -> Dict[str, Any]:
        """Parse SQL code"""
        statements = re.split(r';\s*', code)
        tables = re.findall(r'(?:from|join)\s+(\w+)', code.lower())
        columns = re.findall(r'select\s+(.*?)\s+from', code.lower(), re.DOTALL)
        
        return {
            'language': 'sql',
            'statements': [s.strip() for s in statements if s.strip()],
            'tables': tables,
            'columns': columns,
            'lines': len(code.splitlines()),
            'complexity': len(statements)
        }
    
    def _parse_generic(self, code: str) -> Dict[str, Any]:
        """Generic parser for unsupported languages"""
        return {
            'language': 'unknown',
            'lines': len(code.splitlines()),
            'complexity': len(code.splitlines())
        }
    
    def _calculate_complexity(self, tree) -> str:
        """Calculate cyclomatic complexity for Python"""
        complexity = 1
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.With)):
                complexity += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        
        if complexity <= 5:
            return 'low'
        elif complexity <= 10:
            return 'medium'
        else:
            return 'high'
    
    def _analyze_json_structure(self, data) -> Dict[str, Any]:
        """Analyze JSON structure"""
        if isinstance(data, dict):
            return {
                'type': 'object',
                'keys': list(data.keys()),
                'nested_objects': sum(1 for v in data.values() if isinstance(v, dict)),
                'arrays': sum(1 for v in data.values() if isinstance(v, list))
            }
        elif isinstance(data, list):
            return {
                'type': 'array',
                'length': len(data),
                'item_types': list(set(type(item).__name__ for item in data))
            }
        else:
            return {
                'type': type(data).__name__,
                'value': data
            }


class CodeOptimizer:
    """Optimize and refactor code"""
    
    def __init__(self):
        self.optimization_patterns = {
            'python': self._optimize_python,
            'javascript': self._optimize_javascript,
            'java': self._optimize_java,
            'cpp': self._optimize_cpp
        }
    
    def optimize_code(self, code: str, language: str) -> Tuple[str, List[str]]:
        """Optimize code for better performance and readability"""
        optimizer_func = self.optimization_patterns.get(language, self._optimize_generic)
        return optimizer_func(code)
    
    def _optimize_python(self, code: str) -> Tuple[str, List[str]]:
        """Optimize Python code"""
        optimized_code = code
        optimizations = []
        
        # List comprehensions
        optimized_code, list_comp_count = re.subn(
            r'(\w+)\s*=\s*\[\]\s*\n\s*for\s+(\w+)\s+in\s+([^:]+):\s*\n\s+(\w+)\.append\(([^)]+)\)',
            r'\1 = [\5 for \2 in \3]',
            optimized_code
        )
        if list_comp_count > 0:
            optimizations.append(f"Converted {list_comp_count} loops to list comprehensions")
        
        # String formatting
        optimized_code, format_count = re.subn(
            r'(\w+)\s*=\s*"([^"]*)"\s*\+\s*str\(([^)]+)\)\s*\+\s*"([^"]*)"',
            r'\1 = f"\2{\3}\4"',
            optimized_code
        )
        if format_count > 0:
            optimizations.append(f"Converted {format_count} concatenations to f-strings")
        
        # Remove redundant imports
        lines = optimized_code.split('\n')
        import_lines = [line for line in lines if line.strip().startswith(('import ', 'from '))]
        if len(import_lines) > len(set(import_lines)):
            optimizations.append("Removed duplicate imports")
            lines = list(dict.fromkeys(import_lines)) + [line for line in lines if not line.strip().startswith(('import ', 'from '))]
            optimized_code = '\n'.join(lines)
        
        return optimized_code, optimizations
    
    def _optimize_javascript(self, code: str) -> Tuple[str, List[str]]:
        """Optimize JavaScript code"""
        optimized_code = code
        optimizations = []
        
        # Arrow functions
        optimized_code, arrow_count = re.subn(
            r'function\s*\(([^)]*)\)\s*{\s*return\s+([^}]+);\s*}',
            r'(\1) => \2',
            optimized_code
        )
        if arrow_count > 0:
            optimizations.append(f"Converted {arrow_count} functions to arrow functions")
        
        # Template literals
        optimized_code, template_count = re.subn(
            r'"([^"]*)"\s*\+\s*([^+]+)\s*\+\s*"([^"]*)"',
            r'`\1${\2}\3`',
            optimized_code
        )
        if template_count > 0:
            optimizations.append(f"Converted {template_count} concatenations to template literals")
        
        return optimized_code, optimizations
    
    def _optimize_java(self, code: str) -> Tuple[str, List[str]]:
        """Optimize Java code"""
        optimized_code = code
        optimizations = []
        
        # Enhanced for loops
        optimized_code, for_count = re.subn(
            r'for\s*\(\s*\w+\s+(\w+)\s*:\s*(\w+)\.toArray\(\)\s*\)',
            r'for (\2 \1)',
            optimized_code
        )
        if for_count > 0:
            optimizations.append(f"Optimized {for_count} for loops")
        
        return optimized_code, optimizations
    
    def _optimize_cpp(self, code: str) -> Tuple[str, List[str]]:
        """Optimize C++ code"""
        optimized_code = code
        optimizations = []
        
        # Range-based for loops (C++11)
        optimized_code, range_count = re.subn(
            r'for\s*\(\s*auto\s+(\w+)\s*=\s*(\w+)\.begin\(\);\s*\w+\s*!=\s*\2\.end\(\);\s*\+\+\w+\s*\)',
            r'for (auto \1 : \2)',
            optimized_code
        )
        if range_count > 0:
            optimizations.append(f"Converted {range_count} loops to range-based for")
        
        return optimized_code, optimizations
    
    def _optimize_generic(self, code: str) -> Tuple[str, List[str]]:
        """Generic optimizations"""
        optimizations = []
        
        # Remove trailing whitespace
        lines = code.split('\n')
        cleaned_lines = [line.rstrip() for line in lines]
        if lines != cleaned_lines:
            optimizations.append("Removed trailing whitespace")
        
        # Remove multiple consecutive empty lines
        new_lines = []
        empty_count = 0
        for line in cleaned_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    new_lines.append(line)
            else:
                empty_count = 0
                new_lines.append(line)
        
        if len(new_lines) != len(cleaned_lines):
            optimizations.append("Reduced consecutive empty lines")
        
        return '\n'.join(new_lines), optimizations


class CodeAssistantAgent:
    """Advanced code assistant with AI capabilities"""
    
    def __init__(self):
        self.parser = CodeParser()
        self.optimizer = CodeOptimizer()
        self.llm_client = OllamaClient(
            model=OLLAMA_MODEL,
            api_base=OLLAMA_API_BASE,
            system_message=self._get_system_prompt(),
            classify_prompt=""
        )
        
        self.logger = logging.getLogger("sokol.code_assistant")
        
        # Code templates
        self.templates = {
            'python_function': '''def {function_name}({parameters}):
    """
    {description}
    
    Args:
        {args_doc}
    
    Returns:
        {returns_doc}
    """
    {body}''',
            
            'python_class': '''class {class_name}:
    """
    {description}
    """
    
    def __init__(self{init_params}):
        {init_body}
    
    {methods}''',
            
            'javascript_function': '''function {function_name}({parameters}) {{
    /**
     * {description}
     * @param {{{{params_type}}}} {params_doc}
     * @returns {{{{return_type}}}} {returns_doc}
     */
    {body}
}}''',
            
            'java_class': '''public class {class_name} {{
    /**
     * {description}
     */
    {fields}
    
    public {class_name}({constructor_params}) {{
        {constructor_body}
    }}
    
    {methods}
}}'''
        }
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for code assistant"""
        return """You are an expert programming assistant and code reviewer. You help users with:
1. Writing clean, efficient, and well-documented code
2. Debugging and fixing errors
3. Optimizing code for better performance
4. Explaining complex code concepts
5. Suggesting best practices and design patterns
6. Generating code snippets and templates
7. Refactoring code for better maintainability

Always provide:
- Clean, working code
- Clear explanations
- Best practices
- Error handling
- Performance considerations
- Security recommendations

Focus on readability, maintainability, and efficiency."""
    
    def generate_code(self, request: str, language: str = 'python') -> CodeGeneration:
        """Generate code based on natural language request"""
        try:
            # Create prompt for code generation
            prompt = self._create_code_generation_prompt(request, language)
            
            # Get response from LLM
            response = self.llm_client.chat(prompt, one_shot=True)
            
            # Parse response
            code = self._extract_code_from_response(response, language)
            explanation = self._extract_explanation_from_response(response)
            
            # Analyze generated code
            analysis = self.parser.parse_code(code, language)
            
            # Calculate quality score
            quality_score = self._calculate_code_quality(code, analysis)
            
            # Generate usage example
            usage_example = self._generate_usage_example(code, language)
            
            # Extract dependencies
            dependencies = self._extract_dependencies(code, language)
            
            return CodeGeneration(
                code=code,
                language=language,
                explanation=explanation,
                dependencies=dependencies,
                usage_example=usage_example,
                quality_score=quality_score
            )
            
        except Exception as e:
            self.logger.error(f"Code generation error: {e}")
            return CodeGeneration(
                code=f"// Error generating code: {e}",
                language=language,
                explanation=f"Failed to generate code: {e}",
                dependencies=[],
                usage_example="",
                quality_score=0.0
            )
    
    def analyze_code(self, code: str, language: Optional[str] = None) -> CodeAnalysis:
        """Analyze code for issues and improvements"""
        try:
            # Parse code structure
            parsed = self.parser.parse_code(code, language)
            detected_language = parsed.get('language', 'unknown')
            
            # Create analysis prompt
            prompt = self._create_code_analysis_prompt(code, detected_language)
            
            # Get AI analysis
            response = self.llm_client.chat(prompt, one_shot=True)
            
            # Parse AI response
            issues = self._extract_issues_from_response(response)
            suggestions = self._extract_suggestions_from_response(response)
            optimizations = self._extract_optimizations_from_response(response)
            security_issues = self._extract_security_issues_from_response(response)
            
            # Calculate performance score
            performance_score = self._calculate_performance_score(code, parsed)
            
            return CodeAnalysis(
                language=detected_language,
                complexity=parsed.get('complexity', 'medium'),
                issues=issues,
                suggestions=suggestions,
                optimizations=optimizations,
                security_issues=security_issues,
                performance_score=performance_score
            )
            
        except Exception as e:
            self.logger.error(f"Code analysis error: {e}")
            return CodeAnalysis(
                language=language or 'unknown',
                complexity='unknown',
                issues=[f"Analysis error: {e}"],
                suggestions=[],
                optimizations=[],
                security_issues=[],
                performance_score=0.0
            )
    
    def optimize_code(self, code: str, language: Optional[str] = None) -> Tuple[str, List[str]]:
        """Optimize code for better performance and readability"""
        if not language:
            language = self.parser.detect_language(code)
        
        # Get AI suggestions
        prompt = self._create_optimization_prompt(code, language)
        response = self.llm_client.chat(prompt, one_shot=True)
        
        # Apply automatic optimizations
        optimized_code, auto_optimizations = self.optimizer.optimize_code(code, language)
        
        # Extract AI suggestions
        ai_suggestions = self._extract_optimizations_from_response(response)
        
        # Combine optimizations
        all_optimizations = auto_optimizations + ai_suggestions
        
        return optimized_code, all_optimizations
    
    def debug_code(self, code: str, error_message: str, language: Optional[str] = None) -> Tuple[str, str]:
        """Debug code with error message"""
        if not language:
            language = self.parser.detect_language(code)
        
        # Create debugging prompt
        prompt = self._create_debugging_prompt(code, error_message, language)
        
        # Get AI debugging help
        response = self.llm_client.chat(prompt, one_shot=True)
        
        # Extract fixed code and explanation
        fixed_code = self._extract_code_from_response(response, language)
        explanation = self._extract_explanation_from_response(response)
        
        return fixed_code, explanation
    
    def explain_code(self, code: str, language: Optional[str] = None) -> str:
        """Explain code in natural language"""
        if not language:
            language = self.parser.detect_language(code)
        
        # Create explanation prompt
        prompt = self._create_explanation_prompt(code, language)
        
        # Get AI explanation
        response = self.llm_client.chat(prompt, one_shot=True)
        
        return response
    
    def refactor_code(self, code: str, refactoring_type: str = 'general') -> Tuple[str, List[str]]:
        """Refactor code according to specified type"""
        language = self.parser.detect_language(code)
        
        # Create refactoring prompt
        prompt = self._create_refactoring_prompt(code, language, refactoring_type)
        
        # Get AI refactoring
        response = self.llm_client.chat(prompt, one_shot=True)
        
        # Extract refactored code and changes
        refactored_code = self._extract_code_from_response(response, language)
        changes = self._extract_refactoring_changes_from_response(response)
        
        return refactored_code, changes
    
    def _create_code_generation_prompt(self, request: str, language: str) -> str:
        """Create prompt for code generation"""
        return f"""Generate {language} code for the following request:

Request: {request}

Requirements:
1. Write clean, efficient, and well-documented code
2. Include proper error handling
3. Follow best practices and coding conventions
4. Add comments where necessary
5. Include type hints where applicable
6. Make the code production-ready

Please provide:
- The complete code implementation
- A brief explanation of how it works
- Any dependencies or imports needed
- A simple usage example

Format your response with:
```{language}
[Your code here]
```

Explanation: [Your explanation here]

Dependencies: [List dependencies]

Usage Example: [Example code]"""
    
    def _create_code_analysis_prompt(self, code: str, language: str) -> str:
        """Create prompt for code analysis"""
        return f"""Analyze the following {language} code for potential issues and improvements:

```{language}
{code}
```

Please analyze and provide:
1. Code quality assessment
2. Potential bugs or issues
3. Performance bottlenecks
4. Security vulnerabilities
5. Best practices violations
6. Suggestions for improvement
7. Optimization opportunities

Format your response clearly with sections for each area."""
    
    def _create_optimization_prompt(self, code: str, language: str) -> str:
        """Create prompt for code optimization"""
        return f"""Optimize the following {language} code for better performance and readability:

```{language}
{code}
```

Please provide:
1. Specific optimization techniques
2. Performance improvements
3. Code readability enhancements
4. Best practices implementation
5. Any refactoring suggestions

Focus on practical optimizations that can be applied immediately."""
    
    def _create_debugging_prompt(self, code: str, error_message: str, language: str) -> str:
        """Create prompt for debugging"""
        return f"""Debug the following {language} code that's producing an error:

```{language}
{code}
```

Error message: {error_message}

Please provide:
1. The root cause of the error
2. The fixed code
3. Explanation of the fix
4. Prevention tips for similar issues

Format your response with the fixed code in a code block."""
    
    def _create_explanation_prompt(self, code: str, language: str) -> str:
        """Create prompt for code explanation"""
        return f"""Explain the following {language} code in simple terms:

```{language}
{code}
```

Please provide:
1. Overall purpose of the code
2. Step-by-step explanation of how it works
3. Key concepts and algorithms used
4. Important patterns or techniques
5. Any potential gotchas or edge cases

Make the explanation clear and educational for someone learning to code."""
    
    def _create_refactoring_prompt(self, code: str, language: str, refactoring_type: str) -> str:
        """Create prompt for code refactoring"""
        return f"""Refactor the following {language} code ({refactoring_type} refactoring):

```{language}
{code}
```

Please provide:
1. The refactored code
2. Specific changes made
3. Benefits of the refactoring
4. Any trade-offs or considerations

Common refactoring types: extract method, rename variable, simplify condition, remove duplication, improve structure, etc."""
    
    def _extract_code_from_response(self, response: str, language: str) -> str:
        """Extract code block from AI response"""
        pattern = rf'```{language}\s*\n(.*?)\n```'
        match = re.search(pattern, response, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # Fallback: try to extract any code block
        pattern = r'```\s*\n(.*?)\n```'
        match = re.search(pattern, response, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # No code block found
        return response.strip()
    
    def _extract_explanation_from_response(self, response: str) -> str:
        """Extract explanation from AI response"""
        # Look for explanation section
        if "Explanation:" in response:
            return response.split("Explanation:")[1].strip()
        elif "explanation:" in response:
            return response.split("explanation:")[1].strip()
        else:
            # Return response without code blocks
            cleaned = re.sub(r'```.*?```', '', response, flags=re.DOTALL)
            return cleaned.strip()
    
    def _extract_issues_from_response(self, response: str) -> List[str]:
        """Extract issues from AI response"""
        issues = []
        
        # Look for common issue indicators
        issue_patterns = [
            r'issue:\s*(.+)',
            r'problem:\s*(.+)',
            r'bug:\s*(.+)',
            r'error:\s*(.+)',
            r'warning:\s*(.+)'
        ]
        
        for pattern in issue_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            issues.extend(matches)
        
        return issues[:10]  # Limit to 10 issues
    
    def _extract_suggestions_from_response(self, response: str) -> List[str]:
        """Extract suggestions from AI response"""
        suggestions = []
        
        # Look for suggestion indicators
        suggestion_patterns = [
            r'suggestion:\s*(.+)',
            r'recommendation:\s*(.+)',
            r'consider:\s*(.+)',
            r'improve:\s*(.+)'
        ]
        
        for pattern in suggestion_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            suggestions.extend(matches)
        
        return suggestions[:10]  # Limit to 10 suggestions
    
    def _extract_optimizations_from_response(self, response: str) -> List[str]:
        """Extract optimizations from AI response"""
        optimizations = []
        
        # Look for optimization indicators
        optimization_patterns = [
            r'optimization:\s*(.+)',
            r'optimize:\s*(.+)',
            r'performance:\s*(.+)',
            r'faster:\s*(.+)'
        ]
        
        for pattern in optimization_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            optimizations.extend(matches)
        
        return optimizations[:10]  # Limit to 10 optimizations
    
    def _extract_security_issues_from_response(self, response: str) -> List[str]:
        """Extract security issues from AI response"""
        security_issues = []
        
        # Look for security indicators
        security_patterns = [
            r'security:\s*(.+)',
            r'vulnerability:\s*(.+)',
            r'unsafe:\s*(.+)',
            r'risk:\s*(.+)'
        ]
        
        for pattern in security_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            security_issues.extend(matches)
        
        return security_issues[:10]  # Limit to 10 security issues
    
    def _extract_refactoring_changes_from_response(self, response: str) -> List[str]:
        """Extract refactoring changes from AI response"""
        changes = []
        
        # Look for change indicators
        change_patterns = [
            r'change:\s*(.+)',
            r'refactored:\s*(.+)',
            r'modified:\s*(.+)',
            r'improved:\s*(.+)'
        ]
        
        for pattern in change_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            changes.extend(matches)
        
        return changes[:10]  # Limit to 10 changes
    
    def _extract_dependencies(self, code: str, language: str) -> List[str]:
        """Extract dependencies from code"""
        dependencies = []
        
        if language == 'python':
            # Extract imports
            imports = re.findall(r'import\s+(\w+)', code)
            from_imports = re.findall(r'from\s+(\w+)\s+import', code)
            dependencies = list(set(imports + from_imports))
        
        elif language in ['javascript', 'typescript']:
            # Extract imports and requires
            imports = re.findall(r'import.*from\s+[\'"]([^\'"]+)[\'"]', code)
            requires = re.findall(r'require\([\'"]([^\'"]+)[\'"]\)', code)
            dependencies = list(set(imports + requires))
        
        elif language == 'java':
            # Extract imports
            imports = re.findall(r'import\s+([^;]+);', code)
            dependencies = imports
        
        elif language == 'cpp':
            # Extract includes
            includes = re.findall(r'#include\s*[<"]([^>"]+)[>"]', code)
            dependencies = includes
        
        return dependencies
    
    def _calculate_code_quality(self, code: str, analysis: Dict[str, Any]) -> float:
        """Calculate code quality score"""
        score = 100.0
        
        # Deduct for complexity
        complexity = analysis.get('complexity', 'medium')
        if complexity == 'high':
            score -= 20
        elif complexity == 'medium':
            score -= 10
        
        # Deduct for length (very long code might be complex)
        lines = analysis.get('lines', 0)
        if lines > 500:
            score -= 10
        elif lines > 1000:
            score -= 20
        
        # Bonus for good structure
        if analysis.get('functions') or analysis.get('classes'):
            score += 10
        
        # Bonus for documentation
        if '"""' in code or "'''" in code or '/*' in code:
            score += 10
        
        return max(0.0, min(100.0, score))
    
    def _calculate_performance_score(self, code: str, analysis: Dict[str, Any]) -> float:
        """Calculate performance score"""
        score = 100.0
        
        # Deduct for potential performance issues
        lines = analysis.get('lines', 0)
        if lines > 1000:
            score -= 20
        
        complexity = analysis.get('complexity', 'medium')
        if complexity == 'high':
            score -= 30
        elif complexity == 'medium':
            score -= 15
        
        # Check for common performance anti-patterns
        if 'nested loops' in code.lower():
            score -= 10
        if 'recursive' in code.lower() and lines > 100:
            score -= 10
        
        return max(0.0, min(100.0, score))
    
    def _generate_usage_example(self, code: str, language: str) -> str:
        """Generate usage example for code"""
        # This is a simplified version - could be enhanced with AI
        if language == 'python':
            if 'def ' in code:
                func_name = re.search(r'def\s+(\w+)', code)
                if func_name:
                    return f"# Example usage:\nresult = {func_name.group(1)}()\nprint(result)"
        
        elif language in ['javascript', 'typescript']:
            if 'function ' in code:
                func_name = re.search(r'function\s+(\w+)', code)
                if func_name:
                    return f"// Example usage:\nconst result = {func_name.group(1)}();\nconsole.log(result);"
        
        return "# Usage example not available"


# Global code assistant instance
_code_assistant: Optional[CodeAssistantAgent] = None


def get_code_assistant() -> CodeAssistantAgent:
    """Get global code assistant instance"""
    global _code_assistant
    if _code_assistant is None:
        _code_assistant = CodeAssistantAgent()
    return _code_assistant


if __name__ == "__main__":
    # Test code assistant
    print("Code Assistant Agent Test")
    print("========================")
    
    assistant = CodeAssistantAgent()
    
    # Test code generation
    print("\n1. Testing code generation:")
    result = assistant.generate_code("Create a function that sorts a list of numbers", "python")
    print(f"Generated code quality: {result.quality_score:.1f}")
    print(f"Dependencies: {result.dependencies}")
    
    # Test code analysis
    print("\n2. Testing code analysis:")
    test_code = """
def bubble_sort(arr):
    for i in range(len(arr)):
        for j in range(len(arr) - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
"""
    analysis = assistant.analyze_code(test_code)
    print(f"Language: {analysis.language}")
    print(f"Complexity: {analysis.complexity}")
    print(f"Issues: {len(analysis.issues)}")
    print(f"Suggestions: {len(analysis.suggestions)}")
    
    print("\nCode assistant test completed!")

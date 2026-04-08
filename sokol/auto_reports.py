# -*- coding: utf-8 -*-
"""
SOKOL v8.0 - Auto Reports System
Automatic report generation for system usage, performance, and activities
"""
import os
import json
import time
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import logging

from .config import VERSION, USER_HOME, SOKOL_LOG_DIR
from .memory import ContextMemory

logger = logging.getLogger("sokol.reports")


@dataclass
class ReportData:
    """Report data structure"""
    timestamp: datetime
    report_type: str
    title: str
    content: Dict[str, Any]
    metrics: Dict[str, float]
    summary: str
    recommendations: List[str]


@dataclass
class ActivityEvent:
    """Activity event for tracking"""
    timestamp: datetime
    event_type: str
    description: str
    details: Dict[str, Any]
    user: str
    session_id: str


class ActivityTracker:
    """Track user activities and system events"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.session_id = self._generate_session_id()
        self.current_user = "User"
        self._lock = threading.Lock()
        self._init_database()
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        return f"session_{int(time.time())}_{os.getpid()}"
    
    def _init_database(self):
        """Initialize activity database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    details TEXT,
                    user TEXT,
                    session_id TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    metadata TEXT
                )
            ''')
            
            conn.commit()
    
    def track_activity(self, event_type: str, description: str, details: Optional[Dict[str, Any]] = None):
        """Track an activity event"""
        with self._lock:
            try:
                event = ActivityEvent(
                    timestamp=datetime.now(),
                    event_type=event_type,
                    description=description,
                    details=details or {},
                    user=self.current_user,
                    session_id=self.session_id
                )
                
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute('''
                        INSERT INTO activities 
                        (timestamp, event_type, description, details, user, session_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        event.timestamp.isoformat(),
                        event.event_type,
                        event.description,
                        json.dumps(event.details),
                        event.user,
                        event.session_id
                    ))
                    conn.commit()
                    
            except Exception as e:
                logger.error(f"Failed to track activity: {e}")
    
    def track_metric(self, metric_name: str, value: float, metadata: Optional[Dict[str, Any]] = None):
        """Track a system metric"""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute('''
                        INSERT INTO metrics 
                        (timestamp, metric_name, metric_value, metadata)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        datetime.now().isoformat(),
                        metric_name,
                        value,
                        json.dumps(metadata or {})
                    ))
                    conn.commit()
                    
            except Exception as e:
                logger.error(f"Failed to track metric: {e}")
    
    def get_activities(self, start_time: Optional[datetime] = None, 
                      end_time: Optional[datetime] = None,
                      event_type: Optional[str] = None) -> List[ActivityEvent]:
        """Get activities within time range"""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    query = "SELECT * FROM activities WHERE 1=1"
                    params = []
                    
                    if start_time:
                        query += " AND timestamp >= ?"
                        params.append(start_time.isoformat())
                    
                    if end_time:
                        query += " AND timestamp <= ?"
                        params.append(end_time.isoformat())
                    
                    if event_type:
                        query += " AND event_type = ?"
                        params.append(event_type)
                    
                    query += " ORDER BY timestamp DESC"
                    
                    cursor = conn.execute(query, params)
                    rows = cursor.fetchall()
                    
                    activities = []
                    for row in rows:
                        activities.append(ActivityEvent(
                            timestamp=datetime.fromisoformat(row[1]),
                            event_type=row[2],
                            description=row[3],
                            details=json.loads(row[4]) if row[4] else {},
                            user=row[5],
                            session_id=row[6]
                        ))
                    
                    return activities
                    
            except Exception as e:
                logger.error(f"Failed to get activities: {e}")
                return []
    
    def get_metrics(self, metric_name: Optional[str] = None,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get metrics within time range"""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    query = "SELECT * FROM metrics WHERE 1=1"
                    params = []
                    
                    if metric_name:
                        query += " AND metric_name = ?"
                        params.append(metric_name)
                    
                    if start_time:
                        query += " AND timestamp >= ?"
                        params.append(start_time.isoformat())
                    
                    if end_time:
                        query += " AND timestamp <= ?"
                        params.append(end_time.isoformat())
                    
                    query += " ORDER BY timestamp DESC"
                    
                    cursor = conn.execute(query, params)
                    rows = cursor.fetchall()
                    
                    metrics = []
                    for row in rows:
                        metrics.append({
                            "timestamp": datetime.fromisoformat(row[1]),
                            "metric_name": row[2],
                            "metric_value": row[3],
                            "metadata": json.loads(row[4]) if row[4] else {}
                        })
                    
                    return metrics
                    
            except Exception as e:
                logger.error(f"Failed to get metrics: {e}")
                return []


class ReportGenerator:
    """Generate various types of reports"""
    
    def __init__(self, activity_tracker: ActivityTracker):
        self.activity_tracker = activity_tracker
        self.logger = logging.getLogger("sokol.report_generator")
    
    def generate_daily_report(self, date: Optional[datetime] = None) -> ReportData:
        """Generate daily activity report"""
        if date is None:
            date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        start_time = date
        end_time = date + timedelta(days=1)
        
        # Get activities for the day
        activities = self.activity_tracker.get_activities(start_time, end_time)
        
        # Get metrics for the day
        metrics_data = self.activity_tracker.get_metrics(start_time=start_time, end_time=end_time)
        
        # Analyze activities
        activity_summary = self._analyze_activities(activities)
        
        # Analyze metrics
        metrics_summary = self._analyze_metrics(metrics_data)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(activity_summary, metrics_summary)
        
        # Create report content
        content = {
            "date": date.strftime("%Y-%m-%d"),
            "total_activities": len(activities),
            "activity_breakdown": activity_summary,
            "metrics": metrics_summary,
            "top_commands": self._get_top_commands(activities),
            "productivity_score": self._calculate_productivity_score(activities, metrics_summary)
        }
        
        metrics = {
            "activities_count": len(activities),
            "productivity_score": content["productivity_score"],
            "error_rate": activity_summary.get("error_rate", 0),
            "avg_response_time": metrics_summary.get("avg_response_time", 0)
        }
        
        summary = f"Daily report for {date.strftime('%Y-%m-%d')}: {len(activities)} activities, productivity score: {content['productivity_score']:.1f}"
        
        return ReportData(
            timestamp=datetime.now(),
            report_type="daily",
            title=f"Daily Report - {date.strftime('%Y-%m-%d')}",
            content=content,
            metrics=metrics,
            summary=summary,
            recommendations=recommendations
        )
    
    def generate_weekly_report(self, start_date: Optional[datetime] = None) -> ReportData:
        """Generate weekly activity report"""
        if start_date is None:
            # Start from last Monday
            today = datetime.now().date()
            days_since_monday = today.weekday()
            start_date = datetime.combine(today - timedelta(days=days_since_monday), datetime.min.time())
        
        end_date = start_date + timedelta(days=7)
        
        # Get activities for the week
        activities = self.activity_tracker.get_activities(start_date, end_date)
        
        # Get metrics for the week
        metrics_data = self.activity_tracker.get_metrics(start_time=start_date, end_time=end_date)
        
        # Analyze daily breakdown
        daily_breakdown = self._analyze_daily_breakdown(activities, start_date)
        
        # Weekly trends
        trends = self._analyze_weekly_trends(activities, metrics_data)
        
        # Generate recommendations
        recommendations = self._generate_weekly_recommendations(daily_breakdown, trends)
        
        content = {
            "week_start": start_date.strftime("%Y-%m-%d"),
            "week_end": end_date.strftime("%Y-%m-%d"),
            "total_activities": len(activities),
            "daily_breakdown": daily_breakdown,
            "trends": trends,
            "top_features": self._get_top_features(activities),
            "productivity_trend": self._calculate_productivity_trend(daily_breakdown)
        }
        
        metrics = {
            "activities_count": len(activities),
            "avg_daily_activities": len(activities) / 7,
            "productivity_trend": content["productivity_trend"],
            "feature_usage_diversity": len(content["top_features"])
        }
        
        summary = f"Weekly report {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}: {len(activities)} activities"
        
        return ReportData(
            timestamp=datetime.now(),
            report_type="weekly",
            title=f"Weekly Report - {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            content=content,
            metrics=metrics,
            summary=summary,
            recommendations=recommendations
        )
    
    def generate_performance_report(self, time_range: str = "24h") -> ReportData:
        """Generate system performance report"""
        # Determine time range
        if time_range == "24h":
            start_time = datetime.now() - timedelta(hours=24)
        elif time_range == "7d":
            start_time = datetime.now() - timedelta(days=7)
        elif time_range == "30d":
            start_time = datetime.now() - timedelta(days=30)
        else:
            start_time = datetime.now() - timedelta(hours=24)
        
        end_time = datetime.now()
        
        # Get performance metrics
        cpu_metrics = self.activity_tracker.get_metrics("cpu_usage", start_time, end_time)
        memory_metrics = self.activity_tracker.get_metrics("memory_usage", start_time, end_time)
        response_metrics = self.activity_tracker.get_metrics("response_time", start_time, end_time)
        
        # Analyze performance
        performance_analysis = self._analyze_performance(cpu_metrics, memory_metrics, response_metrics)
        
        # Identify bottlenecks
        bottlenecks = self._identify_bottlenecks(performance_analysis)
        
        # Generate optimization recommendations
        recommendations = self._generate_performance_recommendations(performance_analysis, bottlenecks)
        
        content = {
            "time_range": time_range,
            "performance_analysis": performance_analysis,
            "bottlenecks": bottlenecks,
            "system_health": self._calculate_system_health(performance_analysis),
            "resource_usage_trends": self._calculate_resource_trends(cpu_metrics, memory_metrics)
        }
        
        metrics = {
            "avg_cpu_usage": performance_analysis.get("avg_cpu", 0),
            "avg_memory_usage": performance_analysis.get("avg_memory", 0),
            "avg_response_time": performance_analysis.get("avg_response_time", 0),
            "system_health_score": content["system_health"]["score"]
        }
        
        summary = f"Performance report ({time_range}): CPU {metrics['avg_cpu_usage']:.1f}%, Memory {metrics['avg_memory_usage']:.1f}%, Response {metrics['avg_response_time']:.2f}s"
        
        return ReportData(
            timestamp=datetime.now(),
            report_type="performance",
            title=f"Performance Report - {time_range}",
            content=content,
            metrics=metrics,
            summary=summary,
            recommendations=recommendations
        )
    
    def generate_usage_report(self, feature: Optional[str] = None) -> ReportData:
        """Generate feature usage report"""
        start_time = datetime.now() - timedelta(days=30)  # Last 30 days
        end_time = datetime.now()
        
        # Get activities
        activities = self.activity_tracker.get_activities(start_time, end_time)
        
        if feature:
            # Filter by specific feature
            activities = [a for a in activities if feature.lower() in a.description.lower()]
        
        # Analyze usage patterns
        usage_patterns = self._analyze_usage_patterns(activities)
        
        # Feature popularity
        feature_popularity = self._calculate_feature_popularity(activities)
        
        # User behavior insights
        behavior_insights = self._analyze_user_behavior(activities)
        
        content = {
            "period": "Last 30 days",
            "total_activities": len(activities),
            "usage_patterns": usage_patterns,
            "feature_popularity": feature_popularity,
            "behavior_insights": behavior_insights,
            "peak_usage_times": self._find_peak_usage_times(activities)
        }
        
        metrics = {
            "total_activities": len(activities),
            "unique_features_used": len(feature_popularity),
            "avg_daily_usage": len(activities) / 30,
            "usage_consistency": usage_patterns.get("consistency_score", 0)
        }
        
        summary = f"Usage report (30 days): {len(activities)} activities, {len(feature_popularity)} features used"
        
        return ReportData(
            timestamp=datetime.now(),
            report_type="usage",
            title=f"Usage Report - Last 30 Days",
            content=content,
            metrics=metrics,
            summary=summary,
            recommendations=self._generate_usage_recommendations(usage_patterns, feature_popularity)
        )
    
    def _analyze_activities(self, activities: List[ActivityEvent]) -> Dict[str, Any]:
        """Analyze activities and create summary"""
        if not activities:
            return {
                "total": 0,
                "by_type": {},
                "by_hour": {},
                "error_rate": 0,
                "success_rate": 0
            }
        
        # Group by event type
        by_type = {}
        for activity in activities:
            event_type = activity.event_type
            by_type[event_type] = by_type.get(event_type, 0) + 1
        
        # Group by hour
        by_hour = {}
        for activity in activities:
            hour = activity.timestamp.hour
            by_hour[hour] = by_hour.get(hour, 0) + 1
        
        # Calculate error rate
        error_activities = [a for a in activities if a.event_type == "error"]
        error_rate = len(error_activities) / len(activities) if activities else 0
        success_rate = 1 - error_rate
        
        return {
            "total": len(activities),
            "by_type": by_type,
            "by_hour": by_hour,
            "error_rate": error_rate,
            "success_rate": success_rate,
            "most_active_hour": max(by_hour.items(), key=lambda x: x[1])[0] if by_hour else None
        }
    
    def _analyze_metrics(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze metrics data"""
        if not metrics_data:
            return {}
        
        # Group by metric name
        by_name = {}
        for metric in metrics_data:
            name = metric["metric_name"]
            if name not in by_name:
                by_name[name] = []
            by_name[name].append(metric["metric_value"])
        
        # Calculate statistics for each metric
        analysis = {}
        for name, values in by_name.items():
            if values:
                analysis[name] = {
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values)
                }
        
        return analysis
    
    def _get_top_commands(self, activities: List[ActivityEvent]) -> List[Dict[str, Any]]:
        """Get most used commands"""
        commands = {}
        
        for activity in activities:
            if activity.event_type == "command":
                cmd = activity.description
                commands[cmd] = commands.get(cmd, 0) + 1
        
        # Sort by frequency
        sorted_commands = sorted(commands.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"command": cmd, "count": count}
            for cmd, count in sorted_commands[:10]
        ]
    
    def _calculate_productivity_score(self, activities: List[ActivityEvent], metrics_summary: Dict[str, Any]) -> float:
        """Calculate productivity score"""
        if not activities:
            return 0.0
        
        score = 50.0  # Base score
        
        # Bonus for successful activities
        success_activities = [a for a in activities if a.event_type not in ["error", "failed"]]
        if activities:
            success_rate = len(success_activities) / len(activities)
            score += success_rate * 30
        
        # Bonus for diverse feature usage
        unique_features = len(set(a.event_type for a in activities))
        score += min(unique_features * 2, 20)
        
        # Penalty for high error rate
        error_activities = [a for a in activities if a.event_type == "error"]
        if activities:
            error_rate = len(error_activities) / len(activities)
            score -= error_rate * 40
        
        return max(0.0, min(100.0, score))
    
    def _generate_recommendations(self, activity_summary: Dict[str, Any], metrics_summary: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # Error rate recommendations
        error_rate = activity_summary.get("error_rate", 0)
        if error_rate > 0.1:  # 10% error rate
            recommendations.append("High error rate detected. Consider reviewing failed commands and improving error handling.")
        
        # Activity distribution recommendations
        most_active_hour = activity_summary.get("most_active_hour")
        if most_active_hour and 9 <= most_active_hour <= 17:
            recommendations.append("Peak usage during business hours. Consider optimizing performance for this period.")
        
        # Performance recommendations
        if metrics_summary:
            for metric_name, stats in metrics_summary.items():
                if "response_time" in metric_name.lower() and stats.get("avg", 0) > 2.0:
                    recommendations.append("Slow response times detected. Consider optimizing system performance.")
        
        # Feature usage recommendations
        by_type = activity_summary.get("by_type", {})
        if len(by_type) < 5:
            recommendations.append("Limited feature diversity. Consider exploring more SOKOL features to improve productivity.")
        
        return recommendations
    
    def _analyze_daily_breakdown(self, activities: List[ActivityEvent], start_date: datetime) -> Dict[str, Any]:
        """Analyze daily activity breakdown"""
        daily_data = {}
        
        for i in range(7):
            day = start_date + timedelta(days=i)
            day_activities = [a for a in activities if a.timestamp.date() == day.date()]
            
            daily_data[day.strftime("%Y-%m-%d")] = {
                "count": len(day_activities),
                "success_rate": len([a for a in day_activities if a.event_type != "error"]) / len(day_activities) if day_activities else 0,
                "top_commands": self._get_top_commands(day_activities)[:3]
            }
        
        return daily_data
    
    def _analyze_weekly_trends(self, activities: List[ActivityEvent], metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze weekly trends"""
        trends = {
            "activity_trend": "stable",
            "performance_trend": "stable",
            "feature_adoption": "stable"
        }
        
        # Analyze activity trend (simplified)
        if len(activities) > 0:
            # Group by day and check trend
            daily_counts = {}
            for activity in activities:
                day = activity.timestamp.date()
                daily_counts[day] = daily_counts.get(day, 0) + 1
            
            if len(daily_counts) >= 2:
                days = sorted(daily_counts.keys())
                counts = [daily_counts[day] for day in days]
                
                # Simple trend calculation
                if counts[-1] > counts[0] * 1.2:
                    trends["activity_trend"] = "increasing"
                elif counts[-1] < counts[0] * 0.8:
                    trends["activity_trend"] = "decreasing"
        
        return trends
    
    def _generate_weekly_recommendations(self, daily_breakdown: Dict[str, Any], trends: Dict[str, Any]) -> List[str]:
        """Generate weekly recommendations"""
        recommendations = []
        
        # Activity trend recommendations
        if trends.get("activity_trend") == "decreasing":
            recommendations.append("Activity is decreasing. Consider exploring new features or improving user experience.")
        
        # Consistency recommendations
        daily_counts = [data["count"] for data in daily_breakdown.values()]
        if daily_counts:
            avg_count = sum(daily_counts) / len(daily_counts)
            variance = sum((count - avg_count) ** 2 for count in daily_counts) / len(daily_counts)
            
            if variance > avg_count ** 2:  # High variance
                recommendations.append("Usage pattern is inconsistent. Consider establishing regular usage routines.")
        
        return recommendations
    
    def _get_top_features(self, activities: List[ActivityEvent]) -> List[Dict[str, Any]]:
        """Get most used features"""
        features = {}
        
        for activity in activities:
            feature = activity.event_type
            features[feature] = features.get(feature, 0) + 1
        
        sorted_features = sorted(features.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"feature": feature, "count": count}
            for feature, count in sorted_features[:10]
        ]
    
    def _calculate_productivity_trend(self, daily_breakdown: Dict[str, Any]) -> str:
        """Calculate productivity trend over the week"""
        daily_scores = []
        
        for day_data in daily_breakdown.values():
            score = day_data["success_rate"] * 100
            daily_scores.append(score)
        
        if len(daily_scores) < 2:
            return "insufficient_data"
        
        if daily_scores[-1] > daily_scores[0] * 1.1:
            return "improving"
        elif daily_scores[-1] < daily_scores[0] * 0.9:
            return "declining"
        else:
            return "stable"
    
    def _analyze_performance(self, cpu_metrics: List[Dict[str, Any]], memory_metrics: List[Dict[str, Any]], 
                           response_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance metrics"""
        analysis = {}
        
        # CPU analysis
        if cpu_metrics:
            cpu_values = [m["metric_value"] for m in cpu_metrics]
            analysis["cpu"] = {
                "avg": sum(cpu_values) / len(cpu_values),
                "min": min(cpu_values),
                "max": max(cpu_values),
                "samples": len(cpu_values)
            }
        
        # Memory analysis
        if memory_metrics:
            memory_values = [m["metric_value"] for m in memory_metrics]
            analysis["memory"] = {
                "avg": sum(memory_values) / len(memory_values),
                "min": min(memory_values),
                "max": max(memory_values),
                "samples": len(memory_values)
            }
        
        # Response time analysis
        if response_metrics:
            response_values = [m["metric_value"] for m in response_metrics]
            analysis["response_time"] = {
                "avg": sum(response_values) / len(response_values),
                "min": min(response_values),
                "max": max(response_values),
                "samples": len(response_values)
            }
        
        # Calculate averages for easy access
        if "cpu" in analysis:
            analysis["avg_cpu"] = analysis["cpu"]["avg"]
        if "memory" in analysis:
            analysis["avg_memory"] = analysis["memory"]["avg"]
        if "response_time" in analysis:
            analysis["avg_response_time"] = analysis["response_time"]["avg"]
        
        return analysis
    
    def _identify_bottlenecks(self, performance_analysis: Dict[str, Any]) -> List[str]:
        """Identify performance bottlenecks"""
        bottlenecks = []
        
        # CPU bottleneck
        if performance_analysis.get("avg_cpu", 0) > 80:
            bottlenecks.append("High CPU usage detected")
        
        # Memory bottleneck
        if performance_analysis.get("avg_memory", 0) > 80:
            bottlenecks.append("High memory usage detected")
        
        # Response time bottleneck
        if performance_analysis.get("avg_response_time", 0) > 2.0:
            bottlenecks.append("Slow response times detected")
        
        return bottlenecks
    
    def _generate_performance_recommendations(self, performance_analysis: Dict[str, Any], bottlenecks: List[str]) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []
        
        for bottleneck in bottlenecks:
            if "CPU" in bottleneck:
                recommendations.append("Consider optimizing CPU-intensive operations or upgrading hardware.")
            elif "Memory" in bottleneck:
                recommendations.append("Consider reducing memory usage or adding more RAM.")
            elif "Response" in bottleneck:
                recommendations.append("Consider optimizing code performance or reducing response time.")
        
        return recommendations
    
    def _calculate_system_health(self, performance_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall system health score"""
        score = 100.0
        
        # Deduct for high CPU usage
        cpu_usage = performance_analysis.get("avg_cpu", 0)
        if cpu_usage > 80:
            score -= (cpu_usage - 80) * 2
        elif cpu_usage > 60:
            score -= (cpu_usage - 60)
        
        # Deduct for high memory usage
        memory_usage = performance_analysis.get("avg_memory", 0)
        if memory_usage > 80:
            score -= (memory_usage - 80) * 2
        elif memory_usage > 60:
            score -= (memory_usage - 60)
        
        # Deduct for slow response times
        response_time = performance_analysis.get("avg_response_time", 0)
        if response_time > 2.0:
            score -= (response_time - 2.0) * 20
        elif response_time > 1.0:
            score -= (response_time - 1.0) * 10
        
        score = max(0.0, min(100.0, score))
        
        # Determine status
        if score >= 90:
            status = "excellent"
        elif score >= 70:
            status = "good"
        elif score >= 50:
            status = "fair"
        else:
            status = "poor"
        
        return {
            "score": score,
            "status": status,
            "issues": self._identify_bottlenecks(performance_analysis)
        }
    
    def _calculate_resource_trends(self, cpu_metrics: List[Dict[str, Any]], memory_metrics: List[Dict[str, Any]]) -> Dict[str, str]:
        """Calculate resource usage trends"""
        trends = {}
        
        # CPU trend
        if len(cpu_metrics) > 1:
            recent_cpu = cpu_metrics[-1]["metric_value"]
            older_cpu = cpu_metrics[0]["metric_value"]
            
            if recent_cpu > older_cpu * 1.1:
                trends["cpu"] = "increasing"
            elif recent_cpu < older_cpu * 0.9:
                trends["cpu"] = "decreasing"
            else:
                trends["cpu"] = "stable"
        
        # Memory trend
        if len(memory_metrics) > 1:
            recent_memory = memory_metrics[-1]["metric_value"]
            older_memory = memory_metrics[0]["metric_value"]
            
            if recent_memory > older_memory * 1.1:
                trends["memory"] = "increasing"
            elif recent_memory < older_memory * 0.9:
                trends["memory"] = "decreasing"
            else:
                trends["memory"] = "stable"
        
        return trends
    
    def _analyze_usage_patterns(self, activities: List[ActivityEvent]) -> Dict[str, Any]:
        """Analyze usage patterns"""
        patterns = {
            "most_active_hours": {},
            "most_active_days": {},
            "session_duration": {},
            "consistency_score": 0.0
        }
        
        # Most active hours
        for activity in activities:
            hour = activity.timestamp.hour
            patterns["most_active_hours"][hour] = patterns["most_active_hours"].get(hour, 0) + 1
        
        # Most active days
        for activity in activities:
            day = activity.timestamp.strftime("%A")
            patterns["most_active_days"][day] = patterns["most_active_days"].get(day, 0) + 1
        
        # Calculate consistency score
        if activities:
            daily_counts = {}
            for activity in activities:
                day = activity.timestamp.date()
                daily_counts[day] = daily_counts.get(day, 0) + 1
            
            if len(daily_counts) > 1:
                counts = list(daily_counts.values())
                avg_count = sum(counts) / len(counts)
                variance = sum((count - avg_count) ** 2 for count in counts) / len(counts)
                
                # Consistency score: lower variance = higher consistency
                patterns["consistency_score"] = max(0, 100 - (variance / avg_count * 100)) if avg_count > 0 else 0
        
        return patterns
    
    def _calculate_feature_popularity(self, activities: List[ActivityEvent]) -> List[Dict[str, Any]]:
        """Calculate feature popularity"""
        features = {}
        
        for activity in activities:
            feature = activity.event_type
            features[feature] = features.get(feature, 0) + 1
        
        sorted_features = sorted(features.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"feature": feature, "usage_count": count, "percentage": (count / len(activities) * 100) if activities else 0}
            for feature, count in sorted_features
        ]
    
    def _analyze_user_behavior(self, activities: List[ActivityEvent]) -> Dict[str, Any]:
        """Analyze user behavior patterns"""
        behavior = {
            "command_complexity": "medium",
            "feature_exploration": "medium",
            "error_handling": "good",
            "learning_curve": "improving"
        }
        
        # Analyze command complexity (simplified)
        unique_commands = len(set(a.description for a in activities if a.event_type == "command"))
        total_commands = len([a for a in activities if a.event_type == "command"])
        
        if total_commands > 0:
            complexity_ratio = unique_commands / total_commands
            if complexity_ratio > 0.7:
                behavior["command_complexity"] = "high"
            elif complexity_ratio < 0.3:
                behavior["command_complexity"] = "low"
        
        # Analyze error handling
        error_activities = [a for a in activities if a.event_type == "error"]
        if activities:
            error_rate = len(error_activities) / len(activities)
            if error_rate < 0.05:
                behavior["error_handling"] = "excellent"
            elif error_rate > 0.15:
                behavior["error_handling"] = "needs_improvement"
        
        return behavior
    
    def _find_peak_usage_times(self, activities: List[ActivityEvent]) -> List[Dict[str, Any]]:
        """Find peak usage times"""
        hourly_usage = {}
        
        for activity in activities:
            hour = activity.timestamp.hour
            hourly_usage[hour] = hourly_usage.get(hour, 0) + 1
        
        if not hourly_usage:
            return []
        
        # Find top 3 peak hours
        sorted_hours = sorted(hourly_usage.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"hour": hour, "activity_count": count, "percentage": (count / len(activities) * 100) if activities else 0}
            for hour, count in sorted_hours[:3]
        ]
    
    def _generate_usage_recommendations(self, usage_patterns: Dict[str, Any], feature_popularity: List[Dict[str, Any]]) -> List[str]:
        """Generate usage recommendations"""
        recommendations = []
        
        # Consistency recommendations
        consistency = usage_patterns.get("consistency_score", 0)
        if consistency < 50:
            recommendations.append("Usage pattern is inconsistent. Try to establish regular usage routines.")
        
        # Feature exploration recommendations
        if len(feature_popularity) < 5:
            recommendations.append("Limited feature usage. Consider exploring more SOKOL features to improve productivity.")
        
        # Peak usage recommendations
        peak_hours = usage_patterns.get("most_active_hours", {})
        if peak_hours:
            most_active_hour = max(peak_hours.items(), key=lambda x: x[1])[0]
            if 9 <= most_active_hour <= 17:
                recommendations.append("Peak usage during business hours. System is optimized for this period.")
        
        return recommendations


class AutoReportsSystem:
    """Main auto reports system"""
    
    def __init__(self):
        self.reports_dir = os.path.join(USER_HOME, ".sokol", "reports")
        self.db_path = os.path.join(USER_HOME, ".sokol", "activities.db")
        self.activity_tracker = ActivityTracker(self.db_path)
        self.report_generator = ReportGenerator(self.activity_tracker)
        self.scheduled_reports = {}
        self._lock = threading.Lock()
        
        # Ensure directories exist
        os.makedirs(self.reports_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.logger = logging.getLogger("sokol.reports_system")
    
    def track_activity(self, event_type: str, description: str, details: Optional[Dict[str, Any]] = None):
        """Track an activity event"""
        self.activity_tracker.track_activity(event_type, description, details)
    
    def track_metric(self, metric_name: str, value: float, metadata: Optional[Dict[str, Any]] = None):
        """Track a system metric"""
        self.activity_tracker.track_metric(metric_name, value, metadata)
    
    def generate_report(self, report_type: str, **kwargs) -> ReportData:
        """Generate a specific type of report"""
        if report_type == "daily":
            return self.report_generator.generate_daily_report(kwargs.get("date"))
        elif report_type == "weekly":
            return self.report_generator.generate_weekly_report(kwargs.get("start_date"))
        elif report_type == "performance":
            return self.report_generator.generate_performance_report(kwargs.get("time_range", "24h"))
        elif report_type == "usage":
            return self.report_generator.generate_usage_report(kwargs.get("feature"))
        else:
            raise ValueError(f"Unknown report type: {report_type}")
    
    def save_report(self, report: ReportData, format: str = "json") -> str:
        """Save report to file"""
        timestamp = report.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{report.report_type}_{timestamp}.{format}"
        filepath = os.path.join(self.reports_dir, filename)
        
        try:
            if format == "json":
                report_data = {
                    "timestamp": report.timestamp.isoformat(),
                    "report_type": report.report_type,
                    "title": report.title,
                    "content": report.content,
                    "metrics": report.metrics,
                    "summary": report.summary,
                    "recommendations": report.recommendations
                }
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            elif format == "txt":
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"Report: {report.title}\n")
                    f.write(f"Generated: {report.timestamp}\n")
                    f.write(f"Summary: {report.summary}\n")
                    f.write("\n" + "="*50 + "\n")
                    f.write("Content:\n")
                    f.write(json.dumps(report.content, indent=2, ensure_ascii=False))
                    f.write("\n" + "="*50 + "\n")
                    f.write("Metrics:\n")
                    f.write(json.dumps(report.metrics, indent=2, ensure_ascii=False))
                    f.write("\n" + "="*50 + "\n")
                    f.write("Recommendations:\n")
                    for rec in report.recommendations:
                        f.write(f"- {rec}\n")
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")
            return ""
    
    def get_report_list(self) -> List[Dict[str, Any]]:
        """Get list of saved reports"""
        reports = []
        
        try:
            for filename in os.listdir(self.reports_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.reports_dir, filename)
                    
                    with open(filepath, 'r', encoding='utf-8') as f:
                        report_data = json.load(f)
                    
                    reports.append({
                        "filename": filename,
                        "title": report_data.get("title", "Unknown"),
                        "type": report_data.get("report_type", "unknown"),
                        "timestamp": report_data.get("timestamp"),
                        "summary": report_data.get("summary", "")
                    })
            
            # Sort by timestamp (newest first)
            reports.sort(key=lambda x: x["timestamp"], reverse=True)
            
        except Exception as e:
            self.logger.error(f"Failed to get report list: {e}")
        
        return reports
    
    def schedule_report(self, report_type: str, schedule: str, **kwargs):
        """Schedule automatic report generation"""
        with self._lock:
            self.scheduled_reports[report_type] = {
                "schedule": schedule,
                "kwargs": kwargs,
                "last_run": None,
                "enabled": True
            }
    
    def run_scheduled_reports(self):
        """Run all scheduled reports (should be called periodically)"""
        with self._lock:
            now = datetime.now()
            
            for report_type, config in self.scheduled_reports.items():
                if not config["enabled"]:
                    continue
                
                # Check if it's time to run (simplified - just check if last run was more than 24h ago)
                last_run = config["last_run"]
                if last_run is None or (now - last_run).total_seconds() > 86400:  # 24 hours
                    try:
                        report = self.generate_report(report_type, **config["kwargs"])
                        self.save_report(report)
                        config["last_run"] = now
                        
                        self.logger.info(f"Generated scheduled {report_type} report")
                        
                    except Exception as e:
                        self.logger.error(f"Failed to generate scheduled {report_type} report: {e}")


# Global auto reports system instance
_auto_reports_system: Optional[AutoReportsSystem] = None


def get_auto_reports_system() -> AutoReportsSystem:
    """Get global auto reports system instance"""
    global _auto_reports_system
    if _auto_reports_system is None:
        _auto_reports_system = AutoReportsSystem()
    return _auto_reports_system


if __name__ == "__main__":
    # Test auto reports system
    print("Auto Reports System Test")
    print("=======================")
    
    system = AutoReportsSystem()
    
    # Track some test activities
    system.track_activity("command", "open chrome")
    system.track_activity("command", "send telegram message")
    system.track_activity("error", "Failed to launch application")
    system.track_metric("cpu_usage", 45.2)
    system.track_metric("memory_usage", 62.8)
    
    # Generate reports
    daily_report = system.generate_report("daily")
    print(f"Daily report: {daily_report.summary}")
    
    performance_report = system.generate_report("performance")
    print(f"Performance report: {performance_report.summary}")
    
    usage_report = system.generate_report("usage")
    print(f"Usage report: {usage_report.summary}")
    
    # Save reports
    daily_path = system.save_report(daily_report)
    print(f"Saved daily report to: {daily_path}")
    
    print("\nAuto reports system test completed!")

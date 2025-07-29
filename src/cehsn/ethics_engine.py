"""
Ethics Engine for CubeSat-Enabled Hybrid Survival Network (CEHSN)
Agentic AI module for goal-driven decisions (ethical AI constraints)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EthicalPrinciple(Enum):
    """Core ethical principles for AI decision making"""
    BENEFICENCE = "beneficence"  # Do good
    NON_MALEFICENCE = "non_maleficence"  # Do no harm
    AUTONOMY = "autonomy"  # Respect human agency
    JUSTICE = "justice"  # Fair treatment
    TRANSPARENCY = "transparency"  # Explainable decisions
    ACCOUNTABILITY = "accountability"  # Responsibility for actions
    PRIVACY = "privacy"  # Protect personal information
    SUSTAINABILITY = "sustainability"  # Environmental consideration


class DecisionSeverity(Enum):
    """Severity levels for ethical decisions"""
    LOW = "low"  # Minor operational decisions
    MEDIUM = "medium"  # Significant impact decisions
    HIGH = "high"  # Major consequence decisions
    CRITICAL = "critical"  # Life-threatening decisions


class EthicalViolationType(Enum):
    """Types of potential ethical violations"""
    HARM_TO_HUMANS = "harm_to_humans"
    PRIVACY_BREACH = "privacy_breach"
    UNFAIR_DISCRIMINATION = "unfair_discrimination"
    ENVIRONMENTAL_DAMAGE = "environmental_damage"
    RESOURCE_WASTE = "resource_waste"
    DECEPTION = "deception"
    AUTONOMY_VIOLATION = "autonomy_violation"
    UNAUTHORIZED_ACTION = "unauthorized_action"


@dataclass
class EthicalContext:
    """Context information for ethical decision making"""
    decision_id: str
    decision_type: str
    affected_parties: List[str]  # "humans", "animals", "environment", etc.
    potential_consequences: List[str]
    urgency_level: int  # 1-5 scale
    available_alternatives: List[str]
    resource_constraints: Dict[str, Any] = field(default_factory=dict)
    legal_constraints: List[str] = field(default_factory=list)
    cultural_context: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EthicalRule:
    """Ethical rule or constraint"""
    rule_id: str
    principle: EthicalPrinciple
    description: str
    conditions: Dict[str, Any]  # When this rule applies
    weight: float  # Importance weight (0.0-1.0)
    is_absolute: bool = False  # Cannot be overridden
    exceptions: List[str] = field(default_factory=list)
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EthicalAssessment:
    """Assessment of an ethical decision"""
    decision_id: str
    context: EthicalContext
    applicable_rules: List[EthicalRule]
    ethical_score: float  # 0.0-1.0 (1.0 = most ethical)
    violations: List[EthicalViolationType]
    justification: str
    recommended_action: str
    alternative_actions: List[str]
    confidence: float  # 0.0-1.0
    assessment_time_ms: float
    assessor: str = "ethics_engine"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EthicalDecision:
    """Final ethical decision with audit trail"""
    decision_id: str
    original_proposal: str
    assessment: EthicalAssessment
    final_decision: str
    override_reason: Optional[str] = None
    human_approval_required: bool = False
    human_approver: Optional[str] = None
    implementation_status: str = "pending"  # pending, approved, implemented, rejected
    audit_log: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class EthicsEngine:
    """
    AI Ethics Engine for autonomous decision making
    Ensures all AI decisions comply with ethical principles and constraints
    """
    
    def __init__(self, engine_id: str, ethical_framework: str = "utilitarian"):
        self.engine_id = engine_id
        self.ethical_framework = ethical_framework  # utilitarian, deontological, virtue
        self.is_active = False
        
        # Ethical rules database
        self.ethical_rules: Dict[str, EthicalRule] = {}
        
        # Decision history
        self.decision_history: List[EthicalDecision] = []
        
        # Configuration
        self.human_oversight_threshold = 0.7  # Require human approval if ethics score < 0.7
        self.violation_tolerance = 0.1  # Allow minor violations up to this threshold
        
        # Performance metrics
        self.metrics = {
            "decisions_processed": 0,
            "decisions_approved": 0,
            "decisions_rejected": 0,
            "human_interventions": 0,
            "average_ethical_score": 0.0,
            "average_processing_time_ms": 0.0
        }
        
        # Initialize default ethical rules
        self._initialize_default_rules()
        
        logger.info(f"Ethics Engine {engine_id} initialized with {ethical_framework} framework")
    
    async def start_engine(self) -> bool:
        """Start the ethics engine"""
        try:
            self.is_active = True
            await self._validate_ethical_rules()
            
            logger.info(f"Ethics Engine {self.engine_id} started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start ethics engine: {e}")
            return False
    
    async def stop_engine(self) -> bool:
        """Stop the ethics engine"""
        self.is_active = False
        logger.info(f"Ethics Engine {self.engine_id} stopped")
        return True
    
    async def assess_ethical_decision(self, context: EthicalContext) -> EthicalAssessment:
        """Assess the ethical implications of a decision"""
        if not self.is_active:
            raise RuntimeError("Ethics engine not active")
        
        start_time = datetime.utcnow()
        
        try:
            # Find applicable ethical rules
            applicable_rules = self._find_applicable_rules(context)
            
            # Calculate ethical score
            ethical_score = await self._calculate_ethical_score(context, applicable_rules)
            
            # Identify potential violations
            violations = self._identify_violations(context, applicable_rules)
            
            # Generate justification
            justification = self._generate_justification(context, applicable_rules, ethical_score)
            
            # Recommend action
            recommended_action = self._recommend_action(context, ethical_score, violations)
            
            # Generate alternatives
            alternatives = self._generate_alternatives(context)
            
            # Calculate confidence
            confidence = self._calculate_confidence(context, applicable_rules, ethical_score)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            assessment = EthicalAssessment(
                decision_id=context.decision_id,
                context=context,
                applicable_rules=applicable_rules,
                ethical_score=ethical_score,
                violations=violations,
                justification=justification,
                recommended_action=recommended_action,
                alternative_actions=alternatives,
                confidence=confidence,
                assessment_time_ms=processing_time
            )
            
            # Update metrics
            self.metrics["decisions_processed"] += 1
            self._update_processing_metrics(processing_time, ethical_score)
            
            logger.info(f"Ethical assessment completed for {context.decision_id}: "
                       f"score={ethical_score:.2f}, violations={len(violations)}")
            
            return assessment
            
        except Exception as e:
            logger.error(f"Error in ethical assessment: {e}")
            raise
    
    async def make_ethical_decision(self, context: EthicalContext, 
                                  proposed_action: str) -> EthicalDecision:
        """Make an ethical decision with full audit trail"""
        
        # Perform ethical assessment
        assessment = await self.assess_ethical_decision(context)
        
        # Determine if human approval is required
        requires_approval = (
            assessment.ethical_score < self.human_oversight_threshold or
            any(violation in [EthicalViolationType.HARM_TO_HUMANS, 
                            EthicalViolationType.UNAUTHORIZED_ACTION] 
                for violation in assessment.violations) or
            context.urgency_level >= 4
        )
        
        # Create decision record
        decision = EthicalDecision(
            decision_id=context.decision_id,
            original_proposal=proposed_action,
            assessment=assessment,
            final_decision=assessment.recommended_action,
            human_approval_required=requires_approval
        )
        
        # Add to audit log
        decision.audit_log.append(f"Decision created at {datetime.utcnow().isoformat()}")
        decision.audit_log.append(f"Ethical score: {assessment.ethical_score:.2f}")
        decision.audit_log.append(f"Violations detected: {len(assessment.violations)}")
        
        if requires_approval:
            decision.audit_log.append("Human approval required")
            decision.implementation_status = "pending_approval"
            self.metrics["human_interventions"] += 1
        else:
            decision.audit_log.append("Automatically approved")
            decision.implementation_status = "approved"
            self.metrics["decisions_approved"] += 1
        
        # Store decision
        self.decision_history.append(decision)
        
        # Keep only recent history
        if len(self.decision_history) > 10000:
            self.decision_history = self.decision_history[-10000:]
        
        logger.info(f"Ethical decision made for {context.decision_id}: "
                   f"status={decision.implementation_status}")
        
        return decision
    
    async def add_ethical_rule(self, rule: EthicalRule) -> bool:
        """Add a new ethical rule"""
        try:
            self.ethical_rules[rule.rule_id] = rule
            logger.info(f"Added ethical rule: {rule.rule_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add ethical rule {rule.rule_id}: {e}")
            return False
    
    async def remove_ethical_rule(self, rule_id: str) -> bool:
        """Remove an ethical rule"""
        try:
            if rule_id in self.ethical_rules:
                del self.ethical_rules[rule_id]
                logger.info(f"Removed ethical rule: {rule_id}")
                return True
            else:
                logger.warning(f"Ethical rule {rule_id} not found")
                return False
        except Exception as e:
            logger.error(f"Failed to remove ethical rule {rule_id}: {e}")
            return False
    
    async def approve_decision(self, decision_id: str, approver: str, 
                             override_reason: Optional[str] = None) -> bool:
        """Human approval of a pending decision"""
        try:
            # Find decision
            decision = None
            for d in self.decision_history:
                if d.decision_id == decision_id:
                    decision = d
                    break
            
            if not decision:
                logger.error(f"Decision {decision_id} not found")
                return False
            
            if decision.implementation_status != "pending_approval":
                logger.warning(f"Decision {decision_id} not pending approval")
                return False
            
            # Update decision
            decision.human_approver = approver
            decision.override_reason = override_reason
            decision.implementation_status = "approved"
            decision.audit_log.append(f"Approved by {approver} at {datetime.utcnow().isoformat()}")
            
            if override_reason:
                decision.audit_log.append(f"Override reason: {override_reason}")
            
            self.metrics["decisions_approved"] += 1
            
            logger.info(f"Decision {decision_id} approved by {approver}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to approve decision {decision_id}: {e}")
            return False
    
    async def reject_decision(self, decision_id: str, rejector: str, reason: str) -> bool:
        """Reject a pending decision"""
        try:
            # Find decision
            decision = None
            for d in self.decision_history:
                if d.decision_id == decision_id:
                    decision = d
                    break
            
            if not decision:
                logger.error(f"Decision {decision_id} not found")
                return False
            
            # Update decision
            decision.implementation_status = "rejected"
            decision.audit_log.append(f"Rejected by {rejector} at {datetime.utcnow().isoformat()}")
            decision.audit_log.append(f"Rejection reason: {reason}")
            
            self.metrics["decisions_rejected"] += 1
            
            logger.info(f"Decision {decision_id} rejected by {rejector}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reject decision {decision_id}: {e}")
            return False
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get current status of the ethics engine"""
        return {
            "engine_id": self.engine_id,
            "ethical_framework": self.ethical_framework,
            "is_active": self.is_active,
            "total_rules": len(self.ethical_rules),
            "decisions_in_history": len(self.decision_history),
            "human_oversight_threshold": self.human_oversight_threshold,
            "metrics": self.metrics.copy()
        }
    
    def get_pending_approvals(self) -> List[EthicalDecision]:
        """Get decisions pending human approval"""
        return [
            decision for decision in self.decision_history
            if decision.implementation_status == "pending_approval"
        ]
    
    # Private methods
    
    def _initialize_default_rules(self):
        """Initialize default ethical rules"""
        default_rules = [
            EthicalRule(
                rule_id="no_harm_humans",
                principle=EthicalPrinciple.NON_MALEFICENCE,
                description="Never take actions that could harm humans",
                conditions={"affected_parties": ["humans"]},
                weight=1.0,
                is_absolute=True
            ),
            EthicalRule(
                rule_id="respect_privacy",
                principle=EthicalPrinciple.PRIVACY,
                description="Protect personal and sensitive information",
                conditions={"decision_type": ["data_collection", "surveillance"]},
                weight=0.9
            ),
            EthicalRule(
                rule_id="environmental_protection",
                principle=EthicalPrinciple.SUSTAINABILITY,
                description="Minimize environmental impact",
                conditions={"affected_parties": ["environment"]},
                weight=0.7
            ),
            EthicalRule(
                rule_id="fair_resource_allocation",
                principle=EthicalPrinciple.JUSTICE,
                description="Allocate resources fairly based on need",
                conditions={"decision_type": ["resource_allocation"]},
                weight=0.8
            ),
            EthicalRule(
                rule_id="transparent_operations",
                principle=EthicalPrinciple.TRANSPARENCY,
                description="Operations should be explainable and auditable",
                conditions={},
                weight=0.6
            )
        ]
        
        for rule in default_rules:
            self.ethical_rules[rule.rule_id] = rule
    
    def _find_applicable_rules(self, context: EthicalContext) -> List[EthicalRule]:
        """Find ethical rules applicable to the given context"""
        applicable_rules = []
        
        for rule in self.ethical_rules.values():
            if self._rule_applies(rule, context):
                applicable_rules.append(rule)
        
        # Sort by weight (most important first)
        applicable_rules.sort(key=lambda r: r.weight, reverse=True)
        
        return applicable_rules
    
    def _rule_applies(self, rule: EthicalRule, context: EthicalContext) -> bool:
        """Check if a rule applies to the given context"""
        if not rule.conditions:
            return True  # Universal rule
        
        for condition_key, condition_values in rule.conditions.items():
            if condition_key == "affected_parties":
                if not any(party in context.affected_parties for party in condition_values):
                    return False
            elif condition_key == "decision_type":
                if context.decision_type not in condition_values:
                    return False
            elif condition_key == "urgency_level":
                if context.urgency_level not in condition_values:
                    return False
        
        return True
    
    async def _calculate_ethical_score(self, context: EthicalContext, 
                                     rules: List[EthicalRule]) -> float:
        """Calculate overall ethical score for the decision"""
        if not rules:
            return 0.5  # Neutral score when no rules apply
        
        if self.ethical_framework == "utilitarian":
            return self._calculate_utilitarian_score(context, rules)
        elif self.ethical_framework == "deontological":
            return self._calculate_deontological_score(context, rules)
        elif self.ethical_framework == "virtue":
            return self._calculate_virtue_score(context, rules)
        else:
            # Default to weighted average
            return self._calculate_weighted_score(context, rules)
    
    def _calculate_utilitarian_score(self, context: EthicalContext, 
                                   rules: List[EthicalRule]) -> float:
        """Calculate score based on utilitarian ethics (greatest good)"""
        # Analyze consequences and affected parties
        positive_consequences = 0
        negative_consequences = 0
        
        for consequence in context.potential_consequences:
            if any(keyword in consequence.lower() 
                   for keyword in ["help", "save", "protect", "benefit"]):
                positive_consequences += 1
            elif any(keyword in consequence.lower() 
                    for keyword in ["harm", "damage", "endanger", "cost"]):
                negative_consequences += 1
        
        # Weight by number of affected parties
        affected_weight = len(context.affected_parties)
        
        if positive_consequences + negative_consequences == 0:
            return 0.5
        
        utility_score = (positive_consequences * affected_weight) / \
                       ((positive_consequences + negative_consequences) * affected_weight)
        
        return min(1.0, max(0.0, utility_score))
    
    def _calculate_deontological_score(self, context: EthicalContext, 
                                     rules: List[EthicalRule]) -> float:
        """Calculate score based on deontological ethics (duty-based)"""
        # Check compliance with absolute rules
        for rule in rules:
            if rule.is_absolute:
                # Check if this decision would violate the absolute rule
                if self._would_violate_rule(context, rule):
                    return 0.0  # Absolute violation
        
        # Calculate weighted compliance with non-absolute rules
        total_weight = sum(rule.weight for rule in rules if not rule.is_absolute)
        if total_weight == 0:
            return 1.0  # All absolute rules passed
        
        compliance_score = 0.0
        for rule in rules:
            if not rule.is_absolute:
                if not self._would_violate_rule(context, rule):
                    compliance_score += rule.weight
        
        return compliance_score / total_weight
    
    def _calculate_virtue_score(self, context: EthicalContext, 
                              rules: List[EthicalRule]) -> float:
        """Calculate score based on virtue ethics (character-based)"""
        # Assess virtues demonstrated by the decision
        virtues = {
            "compassion": 0,
            "justice": 0,
            "honesty": 0,
            "courage": 0,
            "temperance": 0
        }
        
        # Analyze decision context for virtues
        if "humans" in context.affected_parties:
            virtues["compassion"] += 1
        
        if "fair" in context.decision_type.lower():
            virtues["justice"] += 1
        
        if context.urgency_level >= 4:
            virtues["courage"] += 1
        
        # Calculate virtue score
        total_virtues = sum(virtues.values())
        max_possible = len(virtues)
        
        return total_virtues / max_possible if max_possible > 0 else 0.5
    
    def _calculate_weighted_score(self, context: EthicalContext, 
                                rules: List[EthicalRule]) -> float:
        """Calculate weighted average score"""
        total_weight = sum(rule.weight for rule in rules)
        if total_weight == 0:
            return 0.5
        
        weighted_score = 0.0
        for rule in rules:
            rule_compliance = 1.0 if not self._would_violate_rule(context, rule) else 0.0
            weighted_score += rule_compliance * rule.weight
        
        return weighted_score / total_weight
    
    def _would_violate_rule(self, context: EthicalContext, rule: EthicalRule) -> bool:
        """Check if the decision would violate a specific rule"""
        # Simplified violation detection based on rule principle
        if rule.principle == EthicalPrinciple.NON_MALEFICENCE:
            return any("harm" in consequence.lower() 
                      for consequence in context.potential_consequences)
        
        elif rule.principle == EthicalPrinciple.PRIVACY:
            return any("privacy" in consequence.lower() or "surveillance" in context.decision_type.lower()
                      for consequence in context.potential_consequences)
        
        elif rule.principle == EthicalPrinciple.JUSTICE:
            return "unfair" in context.decision_type.lower()
        
        elif rule.principle == EthicalPrinciple.TRANSPARENCY:
            return "secret" in context.decision_type.lower()
        
        return False  # Default to no violation
    
    def _identify_violations(self, context: EthicalContext, 
                           rules: List[EthicalRule]) -> List[EthicalViolationType]:
        """Identify potential ethical violations"""
        violations = []
        
        for consequence in context.potential_consequences:
            consequence_lower = consequence.lower()
            
            if "harm" in consequence_lower and "human" in consequence_lower:
                violations.append(EthicalViolationType.HARM_TO_HUMANS)
            elif "privacy" in consequence_lower:
                violations.append(EthicalViolationType.PRIVACY_BREACH)
            elif "unfair" in consequence_lower or "discriminat" in consequence_lower:
                violations.append(EthicalViolationType.UNFAIR_DISCRIMINATION)
            elif "environment" in consequence_lower and "damage" in consequence_lower:
                violations.append(EthicalViolationType.ENVIRONMENTAL_DAMAGE)
            elif "waste" in consequence_lower:
                violations.append(EthicalViolationType.RESOURCE_WASTE)
        
        # Remove duplicates
        return list(set(violations))
    
    def _generate_justification(self, context: EthicalContext, rules: List[EthicalRule],
                              ethical_score: float) -> str:
        """Generate justification for the ethical assessment"""
        if ethical_score >= 0.8:
            return f"Decision is highly ethical (score: {ethical_score:.2f}). " \
                   f"Complies with {len(rules)} applicable ethical rules and " \
                   f"demonstrates strong adherence to {self.ethical_framework} principles."
        
        elif ethical_score >= 0.6:
            return f"Decision is moderately ethical (score: {ethical_score:.2f}). " \
                   f"Generally complies with ethical rules but may have minor concerns."
        
        elif ethical_score >= 0.4:
            return f"Decision has ethical concerns (score: {ethical_score:.2f}). " \
                   f"Violates some ethical principles and requires careful consideration."
        
        else:
            return f"Decision has significant ethical issues (score: {ethical_score:.2f}). " \
                   f"Multiple ethical violations detected. Human oversight strongly recommended."
    
    def _recommend_action(self, context: EthicalContext, ethical_score: float,
                        violations: List[EthicalViolationType]) -> str:
        """Recommend action based on ethical assessment"""
        if ethical_score >= 0.8 and not violations:
            return "APPROVE: Proceed with proposed action"
        
        elif ethical_score >= 0.6:
            return "APPROVE_WITH_MONITORING: Proceed but monitor for issues"
        
        elif ethical_score >= 0.4:
            return "REVIEW_REQUIRED: Seek alternative approach or human approval"
        
        else:
            return "REJECT: Do not proceed with proposed action"
    
    def _generate_alternatives(self, context: EthicalContext) -> List[str]:
        """Generate alternative actions"""
        alternatives = ["Delay decision for further analysis"]
        
        if context.urgency_level <= 2:
            alternatives.append("Seek additional stakeholder input")
        
        if "humans" in context.affected_parties:
            alternatives.append("Implement additional safety measures")
            alternatives.append("Require human confirmation before action")
        
        if len(context.available_alternatives) > 0:
            alternatives.extend(context.available_alternatives)
        
        return alternatives[:5]  # Limit to 5 alternatives
    
    def _calculate_confidence(self, context: EthicalContext, rules: List[EthicalRule],
                            ethical_score: float) -> float:
        """Calculate confidence in the ethical assessment"""
        confidence = 0.5  # Base confidence
        
        # Higher confidence with more applicable rules
        rule_confidence = min(0.3, len(rules) * 0.05)
        confidence += rule_confidence
        
        # Higher confidence with clear ethical score
        if ethical_score >= 0.8 or ethical_score <= 0.2:
            confidence += 0.2  # Clear cases
        
        # Lower confidence with high urgency (less time to analyze)
        if context.urgency_level >= 4:
            confidence -= 0.1
        
        return min(1.0, max(0.0, confidence))
    
    def _update_processing_metrics(self, processing_time_ms: float, ethical_score: float):
        """Update performance metrics"""
        # Update average processing time
        total_decisions = self.metrics["decisions_processed"]
        current_avg = self.metrics["average_processing_time_ms"]
        
        self.metrics["average_processing_time_ms"] = \
            (current_avg * (total_decisions - 1) + processing_time_ms) / total_decisions
        
        # Update average ethical score
        current_avg_score = self.metrics["average_ethical_score"]
        self.metrics["average_ethical_score"] = \
            (current_avg_score * (total_decisions - 1) + ethical_score) / total_decisions
    
    async def _validate_ethical_rules(self):
        """Validate ethical rules for consistency"""
        # Check for conflicting absolute rules
        absolute_rules = [rule for rule in self.ethical_rules.values() if rule.is_absolute]
        
        if len(absolute_rules) > 10:  # Too many absolute rules might cause conflicts
            logger.warning(f"Large number of absolute rules ({len(absolute_rules)}) "
                          "may cause decision conflicts")
        
        logger.info(f"Validated {len(self.ethical_rules)} ethical rules")

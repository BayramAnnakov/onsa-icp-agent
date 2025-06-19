"""Prospect scoring utilities."""

import math
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
import structlog

from models import ICP, Prospect, ProspectScore, Company, Person


class ProspectScorer:
    """
    Intelligent prospect scoring system that evaluates how well prospects
    match the Ideal Customer Profile (ICP).
    """
    
    def __init__(self, scoring_config: Dict[str, Any]):
        self.config = scoring_config
        self.logger = structlog.get_logger().bind(component="scoring")
        
        # Default weights if not provided in config
        self.default_weights = {
            "company_size": 0.2,
            "industry_match": 0.3,
            "role_seniority": 0.2,
            "tech_stack": 0.15,
            "recent_activity": 0.15
        }
        
        self.weights = scoring_config.get("weights", self.default_weights)
        self.thresholds = scoring_config.get("thresholds", {
            "minimum_score": 0.6,
            "high_priority": 0.8
        })
    
    def score_prospect(self, prospect: Prospect, icp: ICP) -> ProspectScore:
        """
        Score a prospect against an ICP.
        
        Args:
            prospect: The prospect to score
            icp: The Ideal Customer Profile to match against
            
        Returns:
            ProspectScore with detailed scoring breakdown
        """
        self.logger.debug(
            "Scoring prospect",
            prospect_id=prospect.id,
            company=prospect.company.name,
            person=f"{prospect.person.first_name} {prospect.person.last_name}"
        )
        
        # Calculate individual component scores
        company_score = self._score_company_match(prospect.company, icp)
        person_score = self._score_person_match(prospect.person, icp)
        intent_score = self._score_buying_intent(prospect, icp)
        engagement_score = self._score_engagement_level(prospect.person)
        
        # Calculate criteria-specific scores
        criteria_scores = self._score_icp_criteria(prospect, icp)
        
        # Calculate weighted total score
        total_score = self._calculate_weighted_score({
            "company_match": company_score,
            "person_match": person_score,
            "intent": intent_score,
            "engagement": engagement_score
        })
        
        # Generate explanation
        explanation, strengths, weaknesses = self._generate_explanation(
            prospect, icp, {
                "company": company_score,
                "person": person_score,
                "intent": intent_score,
                "engagement": engagement_score
            }
        )
        
        score = ProspectScore(
            total_score=total_score,
            company_match_score=company_score,
            person_match_score=person_score,
            intent_score=intent_score,
            engagement_score=engagement_score,
            criteria_scores=criteria_scores,
            score_explanation=explanation,
            strengths=strengths,
            weaknesses=weaknesses
        )
        
        self.logger.info(
            "Prospect scored",
            prospect_id=prospect.id,
            total_score=total_score,
            priority=score.get_priority_level()
        )
        
        return score
    
    def _score_company_match(self, company: Company, icp: ICP) -> float:
        """Score how well the company matches ICP criteria."""
        score_components = []
        
        # Industry match
        if icp.industries and company.industry:
            industry_match = 1.0 if company.industry.lower() in [
                ind.lower() for ind in icp.industries
            ] else 0.0
            score_components.append(("industry", industry_match, 0.4))
        
        # Company size match
        if icp.company_size and company.employee_count:
            size_score = self._score_company_size(company.employee_count, icp.company_size)
            score_components.append(("size", size_score, 0.3))
        
        # Tech stack match
        if icp.tech_stack and company.tech_stack:
            tech_score = self._score_tech_stack_match(company.tech_stack, icp.tech_stack)
            score_components.append(("tech", tech_score, 0.2))
        
        # Geographic match
        if icp.geographic_regions and company.locations:
            geo_score = self._score_geographic_match(company.locations, icp.geographic_regions)
            score_components.append(("geography", geo_score, 0.1))
        
        # Calculate weighted average
        if not score_components:
            return 0.5  # Neutral score if no criteria to match
        
        total_weight = sum(weight for _, _, weight in score_components)
        weighted_score = sum(score * weight for _, score, weight in score_components)
        
        return weighted_score / total_weight if total_weight > 0 else 0.5
    
    def _score_person_match(self, person: Person, icp: ICP) -> float:
        """Score how well the person matches ICP criteria."""
        score_components = []
        
        # Role match
        if icp.target_roles and person.title:
            role_score = self._score_role_match(person.title, icp.target_roles)
            score_components.append(("role", role_score, 0.4))
        
        # Seniority match
        if icp.seniority_levels and person.seniority_level:
            seniority_score = 1.0 if person.seniority_level.lower() in [
                level.lower() for level in icp.seniority_levels
            ] else 0.0
            score_components.append(("seniority", seniority_score, 0.3))
        
        # Skills match
        if icp.tools_used and person.skills:
            skills_score = self._score_skills_match(person.skills, icp.tools_used)
            score_components.append(("skills", skills_score, 0.2))
        
        # Experience level
        if person.years_experience:
            exp_score = self._score_experience_level(person.years_experience)
            score_components.append(("experience", exp_score, 0.1))
        
        # Calculate weighted average
        if not score_components:
            return 0.5
        
        total_weight = sum(weight for _, _, weight in score_components)
        weighted_score = sum(score * weight for _, score, weight in score_components)
        
        return weighted_score / total_weight if total_weight > 0 else 0.5
    
    def _score_buying_intent(self, prospect: Prospect, icp: ICP) -> float:
        """Score buying intent based on recent activities and signals."""
        intent_signals = []
        
        # Recent job changes (higher intent)
        if prospect.person.years_at_company and prospect.person.years_at_company <= 1:
            intent_signals.append(0.8)
        
        # Company growth signals
        if prospect.company.funding_stage and "series" in prospect.company.funding_stage.lower():
            intent_signals.append(0.7)
        
        # Recent social media activity matching pain points
        if prospect.person.recent_posts and icp.pain_points:
            activity_score = self._score_pain_point_mentions(
                prospect.person.recent_posts, icp.pain_points
            )
            intent_signals.append(activity_score)
        
        # Tech stack changes/adoption
        if prospect.company.tech_stack and icp.tech_stack:
            tech_adoption_score = self._score_tech_adoption_intent(
                prospect.company.tech_stack, icp.tech_stack
            )
            intent_signals.append(tech_adoption_score)
        
        return sum(intent_signals) / len(intent_signals) if intent_signals else 0.3
    
    def _score_engagement_level(self, person: Person) -> float:
        """Score engagement level based on social media activity."""
        engagement_score = 0.5  # Default neutral score
        
        # Recent activity
        if person.last_post_date:
            days_since_post = (datetime.now() - person.last_post_date).days
            if days_since_post <= 7:
                engagement_score += 0.3
            elif days_since_post <= 30:
                engagement_score += 0.1
        
        # Activity level
        if person.activity_level:
            activity_multipliers = {
                "high": 0.3,
                "medium": 0.1,
                "low": -0.1
            }
            engagement_score += activity_multipliers.get(person.activity_level.lower(), 0)
        
        # Number of recent posts
        if person.recent_posts:
            post_count = len(person.recent_posts)
            engagement_score += min(0.2, post_count * 0.05)
        
        return max(0.0, min(1.0, engagement_score))
    
    def _score_icp_criteria(self, prospect: Prospect, icp: ICP) -> Dict[str, float]:
        """Score prospect against specific ICP criteria."""
        criteria_scores = {}
        
        for criteria_name, criteria in icp.get_all_criteria().items():
            score = self._score_single_criteria(prospect, criteria)
            criteria_scores[criteria_name] = score
        
        return criteria_scores
    
    def _score_single_criteria(self, prospect: Prospect, criteria) -> float:
        """Score a single ICP criteria."""
        # This is a simplified implementation
        # In practice, you'd have more sophisticated matching logic
        
        if criteria.required:
            # For required criteria, return 0 if not met
            return 1.0 if self._criteria_is_met(prospect, criteria) else 0.0
        else:
            # For optional criteria, return partial scores
            return 0.8 if self._criteria_is_met(prospect, criteria) else 0.2
    
    def _criteria_is_met(self, prospect: Prospect, criteria) -> bool:
        """Check if a criteria is met by the prospect."""
        # Simplified criteria matching
        # In practice, this would be more sophisticated
        return True  # Placeholder
    
    def _calculate_weighted_score(self, component_scores: Dict[str, float]) -> float:
        """Calculate weighted total score from component scores."""
        total_weight = sum(self.weights.get(component, 0.25) for component in component_scores)
        weighted_sum = sum(
            score * self.weights.get(component, 0.25) 
            for component, score in component_scores.items()
        )
        
        return weighted_sum / total_weight if total_weight > 0 else 0.5
    
    def _score_company_size(self, employee_count: int, size_criteria: Dict[str, Any]) -> float:
        """Score company size match."""
        min_size = size_criteria.get("min_employees", 0)
        max_size = size_criteria.get("max_employees", float('inf'))
        ideal_size = size_criteria.get("ideal_employees")
        
        if min_size <= employee_count <= max_size:
            if ideal_size and abs(employee_count - ideal_size) <= ideal_size * 0.2:
                return 1.0  # Perfect match
            return 0.8  # Good match
        else:
            # Partial score based on how far outside the range
            if employee_count < min_size:
                ratio = employee_count / min_size
            else:
                ratio = max_size / employee_count
                
            return max(0.0, ratio * 0.5)
    
    def _score_tech_stack_match(self, company_tech: List[str], icp_tech: List[str]) -> float:
        """Score technology stack overlap."""
        if not company_tech or not icp_tech:
            return 0.0
        
        company_tech_lower = [tech.lower() for tech in company_tech]
        icp_tech_lower = [tech.lower() for tech in icp_tech]
        
        matches = sum(1 for tech in icp_tech_lower if tech in company_tech_lower)
        return matches / len(icp_tech_lower)
    
    def _score_geographic_match(self, locations: List[str], target_regions: List[str]) -> float:
        """Score geographic location match."""
        if not locations or not target_regions:
            return 0.0
        
        locations_lower = [loc.lower() for loc in locations]
        target_regions_lower = [region.lower() for region in target_regions]
        
        matches = sum(
            1 for region in target_regions_lower 
            if any(region in loc for loc in locations_lower)
        )
        
        return matches / len(target_regions_lower)
    
    def _score_role_match(self, title: str, target_roles: List[str]) -> float:
        """Score job title/role match."""
        title_lower = title.lower()
        
        # Exact match
        if title_lower in [role.lower() for role in target_roles]:
            return 1.0
        
        # Partial match (contains keywords)
        for role in target_roles:
            role_words = role.lower().split()
            if any(word in title_lower for word in role_words):
                return 0.7
        
        return 0.0
    
    def _score_skills_match(self, person_skills: List[str], target_tools: List[str]) -> float:
        """Score skills/tools match."""
        if not person_skills or not target_tools:
            return 0.0
        
        person_skills_lower = [skill.lower() for skill in person_skills]
        target_tools_lower = [tool.lower() for tool in target_tools]
        
        matches = sum(1 for tool in target_tools_lower if tool in person_skills_lower)
        return matches / len(target_tools_lower)
    
    def _score_experience_level(self, years_experience: int) -> float:
        """Score experience level appropriateness."""
        # Assume 3-15 years is ideal range
        if 3 <= years_experience <= 15:
            return 1.0
        elif 1 <= years_experience < 3:
            return 0.7
        elif 15 < years_experience <= 25:
            return 0.8
        else:
            return 0.5
    
    def _score_pain_point_mentions(self, recent_posts: List[Dict[str, Any]], pain_points: List[str]) -> float:
        """Score mentions of pain points in recent posts."""
        if not recent_posts or not pain_points:
            return 0.0
        
        mentions = 0
        total_posts = len(recent_posts)
        
        for post in recent_posts:
            post_content = post.get("content", "").lower()
            for pain_point in pain_points:
                if pain_point.lower() in post_content:
                    mentions += 1
                    break  # Count max one mention per post
        
        return mentions / total_posts if total_posts > 0 else 0.0
    
    def _score_tech_adoption_intent(self, current_tech: List[str], target_tech: List[str]) -> float:
        """Score intent to adopt target technologies."""
        if not current_tech or not target_tech:
            return 0.0
        
        current_tech_lower = [tech.lower() for tech in current_tech]
        target_tech_lower = [tech.lower() for tech in target_tech]
        
        # Higher score if they're using complementary technologies
        complementary_score = 0.0
        for tech in target_tech_lower:
            if any(related in current_tech_lower for related in self._get_related_tech(tech)):
                complementary_score += 0.2
        
        return min(1.0, complementary_score)
    
    def _get_related_tech(self, technology: str) -> List[str]:
        """Get related technologies that indicate readiness to adopt target tech."""
        # Simplified mapping - in practice, this would be more comprehensive
        tech_relationships = {
            "kubernetes": ["docker", "containerization", "microservices"],
            "react": ["javascript", "nodejs", "frontend"],
            "python": ["data science", "machine learning", "backend"],
            "aws": ["cloud", "devops", "infrastructure"]
        }
        
        return tech_relationships.get(technology.lower(), [])
    
    def _generate_explanation(
        self, 
        prospect: Prospect,
        icp: ICP,
        component_scores: Dict[str, float]
    ) -> Tuple[str, List[str], List[str]]:
        """Generate human-readable explanation of the score."""
        strengths = []
        weaknesses = []
        
        # Analyze component scores
        for component, score in component_scores.items():
            if score >= 0.7:
                strengths.append(self._get_strength_message(component, score, prospect))
            elif score <= 0.4:
                weaknesses.append(self._get_weakness_message(component, score, prospect))
        
        # Generate overall explanation
        total_score = sum(component_scores.values()) / len(component_scores)
        
        if total_score >= 0.8:
            explanation = f"Excellent match for {prospect.company.name}. Strong alignment with ICP across multiple dimensions."
        elif total_score >= 0.6:
            explanation = f"Good potential match for {prospect.company.name}. Some areas of strong alignment."
        else:
            explanation = f"Limited match for {prospect.company.name}. May require further qualification."
        
        return explanation, strengths, weaknesses
    
    def _get_strength_message(self, component: str, score: float, prospect: Prospect) -> str:
        """Get strength message for a component."""
        messages = {
            "company": f"Strong company match - {prospect.company.name} aligns well with target profile",
            "person": f"Good person match - {prospect.person.title} role fits target criteria",
            "intent": f"High buying intent signals detected",
            "engagement": f"Active social media engagement indicates accessibility"
        }
        return messages.get(component, f"Strong {component} alignment")
    
    def _get_weakness_message(self, component: str, score: float, prospect: Prospect) -> str:
        """Get weakness message for a component."""
        messages = {
            "company": f"Company profile may not fully align with ICP requirements",
            "person": f"Person's role or seniority may not match target criteria",
            "intent": f"Limited buying intent signals observed",
            "engagement": f"Low recent activity may indicate limited accessibility"
        }
        return messages.get(component, f"Limited {component} alignment")
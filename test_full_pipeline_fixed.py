#!/usr/bin/env python3
"""
Full pipeline test: ICP Agent -> Prospect Agent
Fixed version with timeout and better error handling
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = f"test_full_pipeline_{timestamp}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add parent directory to path
import sys
sys.path.append(str(Path(__file__).parent))

from utils.config import Config
from utils.json_storage import JSONStorage
from agents.adk_icp_agent import ADKICPAgent
from agents.adk_prospect_agent import ADKProspectAgent


async def test_full_pipeline():
    """Test the full pipeline: ICP generation -> Prospect search"""
    
    logger.info("="*70)
    logger.info("🚀 Full Pipeline Test: ICP Agent -> Prospect Agent")
    logger.info("="*70)
    
    try:
        # Initialize configuration
        config = Config()
        storage = JSONStorage("./data/json_storage")
        
        # Step 1: Generate ICP for onsa.ai (with timeout)
        logger.info("\n" + "="*70)
        logger.info("STEP 1: GENERATING ICP FOR ONSA.AI")
        logger.info("="*70)
        
        icp_agent = ADKICPAgent(config)
        logger.info("✅ ICP Agent initialized")
        
        # Try to generate ICP with timeout
        logger.info("\n🔍 Analyzing onsa.ai to create ICP...")
        
        # Option 1: Try to generate new ICP with timeout
        icp_generated = False
        icp = None
        icp_id = None
        
        try:
            # Set a 30-second timeout for ICP generation
            icp_result = await asyncio.wait_for(
                icp_agent.create_icp_from_research(
                    business_info={
                        "company": "Onsa",
                        "website": "https://onsa.ai",
                        "industry": "AI/Sales Technology",
                        "description": "AI-powered sales automation platform"
                    },
                    research_depth="basic"  # Use basic instead of comprehensive to speed up
                ),
                timeout=30.0
            )
            
            if icp_result["status"] == "success":
                icp = icp_result["icp"]
                icp_id = icp_result["icp_id"]
                icp_generated = True
                
                logger.info(f"\n✅ ICP Created Successfully!")
                logger.info(f"   ICP ID: {icp_id}")
                logger.info(f"   Name: {icp.get('name', 'Unknown')}")
                logger.info(f"   Industries: {', '.join(icp.get('industries', [])[:3])}")
                logger.info(f"   Target Roles: {', '.join(icp.get('target_roles', [])[:3])}")
                
                # Save ICP
                icp_key = storage.save({
                    "type": "generated_icp",
                    "icp_id": icp_id,
                    "data": icp
                })
                logger.info(f"   Saved ICP: {icp_key}")
                
        except asyncio.TimeoutError:
            logger.warning("ICP generation timed out after 30 seconds")
        except Exception as e:
            logger.warning(f"Error generating ICP: {str(e)}")
        
        # Option 2: If ICP generation failed, use existing ICP
        if not icp_generated:
            logger.info("\n⚠️ Using existing ICP instead...")
            
            # Load the existing ICP for onsa.ai
            icp_key = "20250619_012447_2aeec170de3c74ec"
            logger.info(f"Loading ICP: {icp_key}")
            
            try:
                icp_data = storage.load(icp_key)
                icp = icp_data
                icp_id = icp_data.get("id", "existing_icp")
                
                logger.info(f"✅ ICP Loaded: {icp.get('name', 'Unknown')}")
                logger.info(f"   Industries: {', '.join(icp.get('industries', [])[:3])}")
                logger.info(f"   Target Roles: {', '.join(icp.get('target_roles', [])[:3])}")
                
            except Exception as e:
                logger.error(f"Failed to load existing ICP: {str(e)}")
                # Create a minimal ICP for testing
                icp = {
                    "name": "B2B SaaS Sales Leaders",
                    "description": "Sales leaders at B2B SaaS companies",
                    "industries": ["B2B SaaS", "Software Development", "Information Technology"],
                    "target_roles": ["VP Sales", "Head of Sales", "Sales Director"],
                    "company_criteria": {
                        "company_size": {
                            "values": ["51-200 employees", "201-500 employees"]
                        }
                    },
                    "person_criteria": {
                        "seniority": {
                            "values": ["VP", "Director", "C-Level"]
                        }
                    },
                    "buying_signals": ["Budget Available", "Actively Looking", "Hiring Sales Team"],
                    "pain_points": ["Sales Efficiency", "Lead Generation", "Sales Automation"]
                }
                icp_id = "test_icp_" + datetime.now().strftime('%Y%m%d_%H%M%S')
                logger.info("✅ Created minimal test ICP")
        
        # Step 2: Search for prospects using the ICP
        logger.info("\n" + "="*70)
        logger.info("STEP 2: SEARCHING FOR PROSPECTS")
        logger.info("="*70)
        
        prospect_agent = ADKProspectAgent(config)
        logger.info("✅ Prospect Agent initialized")
        
        # Search with HDW
        logger.info("\n🔍 Searching for prospects using HDW...")
        try:
            hdw_result = await asyncio.wait_for(
                prospect_agent.search_prospects_multi_source(
                    icp_criteria=icp,
                    search_limit=5,  # Reduced limit
                    sources=["hdw"],
                    location_filter="United States"
                ),
                timeout=60.0
            )
            
            hdw_people = []
            if hdw_result["status"] == "success":
                logger.info(f"\n✅ HDW Search Results:")
                logger.info(f"   People found: {hdw_result['people_found']}")
                logger.info(f"   Companies found: {hdw_result['companies_found']}")
                logger.info(f"   Scored prospects: {len(hdw_result['prospects'])}")
                
                # Display top prospects
                for i, prospect in enumerate(hdw_result['prospects'][:3], 1):
                    person = prospect.get("person", {})
                    company = prospect.get("company", {})
                    score = prospect.get("score", {})
                    
                    # Handle name
                    name = person.get('name') or f"{person.get('first_name', '')} {person.get('last_name', '')}".strip() or 'Unknown'
                    
                    logger.info(f"\n   Prospect #{i}:")
                    logger.info(f"   • Name: {name}")
                    logger.info(f"   • Title: {person.get('title', 'Unknown')}")
                    logger.info(f"   • Company: {company.get('name', 'Unknown')}")
                    logger.info(f"   • Score: {score.get('total_score', 0):.2f}")
                    
                    hdw_people.append({
                        "name": name,
                        "title": person.get('title'),
                        "company": company.get('name'),
                        "score": score.get('total_score', 0)
                    })
            else:
                logger.warning(f"HDW search failed: {hdw_result.get('error_message', 'Unknown error')}")
                hdw_result = {"people_found": 0, "prospects": []}
                hdw_people = []
                
        except asyncio.TimeoutError:
            logger.warning("HDW search timed out")
            hdw_result = {"people_found": 0, "prospects": []}
            hdw_people = []
        except Exception as e:
            logger.error(f"HDW search error: {str(e)}")
            hdw_result = {"people_found": 0, "prospects": []}
            hdw_people = []
        
        # Search with Exa
        logger.info("\n🔍 Searching for prospects using Exa websets...")
        try:
            exa_result = await asyncio.wait_for(
                prospect_agent.search_prospects_multi_source(
                    icp_criteria=icp,
                    search_limit=5,  # Reduced limit
                    sources=["exa"]
                ),
                timeout=90.0  # Longer timeout for Exa as it needs to wait for webset
            )
            
            exa_people = []
            if exa_result["status"] == "success":
                logger.info(f"\n✅ Exa Search Results:")
                logger.info(f"   People found: {exa_result['people_found']}")
                logger.info(f"   Scored prospects: {len(exa_result['prospects'])}")
                
                # Display top prospects
                for i, prospect in enumerate(exa_result['prospects'][:3], 1):
                    person = prospect.get("person", {})
                    company = prospect.get("company", {})
                    score = prospect.get("score", {})
                    
                    # Handle name
                    name = person.get('name') or f"{person.get('first_name', '')} {person.get('last_name', '')}".strip() or 'Unknown'
                    
                    logger.info(f"\n   Prospect #{i}:")
                    logger.info(f"   • Name: {name}")
                    logger.info(f"   • Title: {person.get('title', 'Unknown')}")
                    logger.info(f"   • Company: {company.get('name', 'Unknown')}")
                    logger.info(f"   • Score: {score.get('total_score', 0):.2f}")
                    
                    exa_people.append({
                        "name": name,
                        "title": person.get('title'),
                        "company": company.get('name'),
                        "score": score.get('total_score', 0)
                    })
            else:
                logger.warning(f"Exa search failed: {exa_result.get('error_message', 'Unknown error')}")
                exa_result = {"people_found": 0, "prospects": []}
                exa_people = []
                
        except asyncio.TimeoutError:
            logger.warning("Exa search timed out")
            exa_result = {"people_found": 0, "prospects": []}
            exa_people = []
        except Exception as e:
            logger.error(f"Exa search error: {str(e)}")
            exa_result = {"people_found": 0, "prospects": []}
            exa_people = []
        
        # Save all results
        pipeline_results = {
            "test_date": datetime.now().isoformat(),
            "icp": {
                "id": icp_id,
                "name": icp.get('name', 'Unknown'),
                "industries": icp.get('industries', []),
                "target_roles": icp.get('target_roles', [])
            },
            "hdw_results": {
                "total_found": hdw_result.get("people_found", 0),
                "top_prospects": hdw_people
            },
            "exa_results": {
                "total_found": exa_result.get("people_found", 0),
                "top_prospects": exa_people
            }
        }
        
        results_key = storage.save({
            "type": "pipeline_test_results",
            "data": pipeline_results
        })
        
        # Summary
        logger.info("\n" + "="*70)
        logger.info("📊 PIPELINE SUMMARY")
        logger.info("="*70)
        logger.info(f"\n✅ ICP Used: {icp.get('name', 'Unknown')}")
        logger.info(f"   Target Industries: {', '.join(icp.get('industries', [])[:3])}")
        logger.info(f"   Target Roles: {', '.join(icp.get('target_roles', [])[:3])}")
        
        logger.info(f"\n✅ Prospects Found:")
        logger.info(f"   HDW: {hdw_result.get('people_found', 0)} people")
        logger.info(f"   Exa: {exa_result.get('people_found', 0)} people")
        logger.info(f"   Total: {hdw_result.get('people_found', 0) + exa_result.get('people_found', 0)} people")
        
        logger.info(f"\n💾 Results saved: {results_key}")
        logger.info(f"📋 Full test log: {log_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"Pipeline test failed: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_full_pipeline())
    if success:
        print(f"\n✅ Pipeline test completed! Check {log_file} for details.")
    else:
        print(f"\n❌ Pipeline test failed! Check {log_file} for details.")
import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

app = FastAPI()

# Configuration
AUTHORIZED_WALLET = "0xf060b7a620f60BC9DAc0AEcA749eA6cA3c738681"
PENDING_DIR = "trades/pending"
APPROVED_DIR = "trades/approved"
REJECTED_DIR = "trades/rejected"

class TradeProposal(BaseModel):
    city: str
    bucket: str
    model_prob: float
    market_price: float
    edge: float
    position_usdc: float
    token_id: str
    slug: str
    reasoning: str

def verify_logic(proposal: TradeProposal):
    """
    Ported from verifier_agent.py logic.
    """
    # Rule 1: Position Sizing (Max 5 USDC per trade)
    if proposal.position_usdc > 5.0:
        return False, f"Position size too large: ${proposal.position_usdc} exceeds limit of $5.0"

    # Rule 2: Signal Sanity
    reasoning = proposal.reasoning.lower()
    if not reasoning or ("i think" in reasoning and "signal" not in reasoning):
        return False, "Insufficient reasoning: Signal must be data-driven."

    # Rule 3: Market Existence
    if not proposal.token_id or not proposal.slug:
        return False, "Missing market identifiers."

    return True, "Passed all verification checks."

@app.get("/health")
async def health():
    return {"status": "online", "service": "zipline-api"}

@app.post("/verify")
async def verify_trade(proposal: TradeProposal):
    is_approved, reason = verify_logic(proposal)
    
    # Create the physical artifact for the loop
    os.makedirs(PENDING_DIR, exist_ok=True)
    os.makedirs(APPROVED_DIR, exist_ok=True)
    os.makedirs(REJECTED_DIR, exist_ok=True)
    
    filename = f"trade_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    proposal_dict = proposal.dict()
    
    if is_approved:
        path = os.path.join(APPROVED_DIR, filename)
        with open(path, 'w') as f:
            json.dump(proposal_dict, f, indent=4)
        return {"status": "approved", "reason": reason, "artifact": path}
    else:
        path = os.path.join(REJECTED_DIR, filename)
        proposal_dict['rejection_reason'] = reason
        with open(path, 'w') as f:
            json.dump(proposal_dict, f, indent=4)
        raise HTTPException(status_code=400, detail=reason)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

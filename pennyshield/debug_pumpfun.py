#!/usr/bin/env python3
"""
Debug Pump.fun discovery - trace each step
"""

import sys
import os
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace')

from pennyshield.solana.detectors import SolanaRPC, PUMP_FUN_PROGRAM_ID, PUMP_CREATE_DISCRIMINATORS

def debug_pumpfun_discovery():
    print("=" * 60)
    print("Pump.fun Discovery Debug")
    print("=" * 60)
    
    rpc = SolanaRPC()
    
    # 1. Check program ID
    print(f"\n[1] Pump.fun Program ID: {PUMP_FUN_PROGRAM_ID}")
    print(f"    Discriminators: {list(PUMP_CREATE_DISCRIMINATORS.keys())}")
    
    # 2. Get signatures for program
    print("\n[2] Fetching signatures for Pump.fun program...")
    signatures = rpc.get_signatures_for_address(PUMP_FUN_PROGRAM_ID, limit=20)
    print(f"    Found {len(signatures)} signatures")
    
    if not signatures:
        print("    No signatures returned - possible RPC issue")
        return
    
    # Show first few signatures
    for i, sig_info in enumerate(signatures[:5]):
        print(f"    {i+1}. {sig_info.get('signature', 'N/A')[:20]}... slot={sig_info.get('slot')} time={sig_info.get('blockTime')}")
    
    # 3. Try to fetch and parse first few transactions
    print("\n[3] Attempting to fetch and parse transactions...")
    for i, sig_info in enumerate(signatures[:10]):
        signature = sig_info.get('signature')
        if not signature:
            continue
            
        print(f"\n    Checking {i+1}: {signature[:20]}...")
        tx = rpc.get_transaction(signature)
        if not tx:
            print(f"      No transaction returned")
            continue
            
        meta = tx.get('meta', {})
        if meta.get('err'):
            print(f"      Transaction failed: {meta.get('err')}")
            continue
            
        message = tx.get('transaction', {}).get('message', {})
        account_keys = [key.get('pubkey', '') if isinstance(key, dict) else key 
                       for key in message.get('accountKeys', [])]
        
        # Check outer instructions
        instructions = message.get('instructions', [])
        print(f"      Outer instructions: {len(instructions)}")
        
        # Check inner instructions
        inner_groups = meta.get('innerInstructions', [])
        total_inner = sum(len(g.get('instructions', [])) for g in inner_groups)
        print(f"      Inner instruction groups: {len(inner_groups)} ({total_inner} total)")
        
        # Check each instruction for Pump.fun program
        all_ix = []
        for ix in instructions:
            all_ix.append(('outer', ix))
        for group in inner_groups:
            for ix in group.get('instructions', []):
                all_ix.append(('inner', ix))
        
        pumpfun_ix_count = 0
        for ix_type, instruction in all_ix:
            program_id = instruction.get('programId')
            program_index = instruction.get('programIdIndex')
            if not program_id and isinstance(program_index, int) and program_index < len(account_keys):
                program_id = account_keys[program_index]
            
            if program_id == PUMP_FUN_PROGRAM_ID:
                pumpfun_ix_count += 1
                data = instruction.get('data', '')
                if data:
                    try:
                        import base64
                        raw = base64.b64decode(data)
                        if len(raw) >= 8:
                            disc = raw[:8]
                            is_create = disc in PUMP_CREATE_DISCRIMINATORS
                            print(f"      ✅ Pump.fun {ix_type} instruction: discriminator={disc.hex()}, is_create={is_create}")
                            if is_create:
                                # Try to parse
                                from pennyshield.solana.detectors import _decode_create_args
                                try:
                                    args = _decode_create_args(raw)
                                    print(f"         Parsed args: {args}")
                                except Exception as e:
                                    print(f"         Parse error: {e}")
                        else:
                            print(f"      Pump.fun {ix_type} instruction: no data")
                    except Exception as e:
                        print(f"      Decode error: {e}")
        
        if pumpfun_ix_count == 0:
            print(f"      No Pump.fun instructions in this transaction")
        
        if pumpfun_ix_count > 0:
            break  # Found one with Pump.fun instructions
    
    print("\n" + "=" * 60)
    print("Debug complete")

if __name__ == "__main__":
    debug_pumpfun_discovery()
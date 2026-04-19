#!/usr/bin/env python3
"""Debug: print raw NA results structure for one meet to identify field names."""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()


async def main():
    from app.services.racing_api import get_na_meets, get_na_meet_results

    meets_data = await get_na_meets("2026-04-18")
    meets = meets_data.get("meets", [])
    print(f"Total meets: {len(meets)}")

    for meet in meets[:3]:
        meet_id = meet.get("meet_id", "")
        print(f"\nMeet: {meet_id} — {meet.get('track_name', '')}")
        try:
            results_data = await get_na_meet_results(meet_id)
            races = results_data.get("races", [])
            print(f"  Races in results: {len(races)}")
            if races:
                race = races[0]
                print(f"  Race keys: {list(race.keys())}")
                runners = race.get("runners", [])
                print(f"  Runner count: {len(runners)}")
                if runners:
                    r = runners[0]
                    print(f"  Runner keys: {list(r.keys())}")
                    print(f"  Runner sample: {json.dumps(r, indent=2, default=str)}")
        except Exception as e:
            print(f"  Error: {e}")


asyncio.run(main())

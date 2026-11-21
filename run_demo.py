import asyncio
from agents.manager import UnderwritingManager
from state import print_trace

CASES = {
 "sanction": "Applicant: Ravi Kumar. Net monthly income Rs 60,000. Existing EMIs Rs 5,000. Requesting a loan of Rs 5,00,000 for 36 months.",
 "decline (unaffordable)": "Applicant: Neha Singh. Net monthly income Rs 30,000. Existing EMIs Rs 5,000. Requesting a loan of Rs 10,00,000 for 24 months.",
 "returning applicant (long-term memory)": "Applicant: Ravi Kumar. Net monthly income Rs 60,000. Requesting a loan of Rs 1,00,000 for 12 months.",
 "refer (income missing)": "Applicant: Meera Shah. Existing EMIs Rs 3,000. Requesting a loan of Rs 3,00,000 for 24 months.",
}

async def main():
    m = UnderwritingManager()
    for title, text in CASES.items():
        print("\n" + "=" * 70 + f"\nCASE: {title}\n" + "=" * 70)
        print_trace(await m.underwrite(text))

if __name__ == "__main__":
    asyncio.run(main())

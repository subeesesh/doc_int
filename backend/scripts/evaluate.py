"""CLI Evaluation script to seed an evaluation dataset and run benchmarks."""
import sys
import asyncio
from app.db.database import SessionLocal
from app.services.evaluation_service import EvaluationService
from app.models.evaluation import EvaluationDataset


BENCHMARK_QUESTIONS = [
    {
        "question": "How many annual leave days does a full-time employee receive?",
        "ground_truth": "Full-time employees receive 25 days of paid annual leave per calendar year.",
    },
    {
        "question": "How many days per week can an employee work remotely?",
        "ground_truth": "Employees are eligible to work remotely up to 2 days per week with manager approval.",
    },
    {
        "question": "How long do employees have to submit expense claims?",
        "ground_truth": "Expense claims must be submitted within 30 days of incurring the expense.",
    },
    {
        "question": "What is the learning and development budget?",
        "ground_truth": "Full-time employees have an annual learning and development budget of $1,500.",
    },
    {
        "question": "When is manager approval required for remote work?",
        "ground_truth": "Manager approval is required for all remote work arrangements exceeding the standard policy.",
    },
    {
        "question": "What is the receipt threshold for expenses?",
        "ground_truth": "Receipts are mandatory for any individual business expense exceeding $25.",
    },
    {
        "question": "What are the standard working hours?",
        "ground_truth": "Standard working hours are 9:00 AM to 5:00 PM, Monday through Friday, 37.5 hours per week.",
    },
    {
        "question": "What security measures are required for company systems?",
        "ground_truth": "All systems require multi-factor authentication (MFA), screen locking, and disk encryption.",
    },
]


async def run():
    db = SessionLocal()
    try:
        eval_svc = EvaluationService(db)

        # 1. Create or get benchmark dataset
        dataset_name = "EDI Ground Truth Benchmark"
        ds = db.query(EvaluationDataset).filter(EvaluationDataset.name == dataset_name).first()
        if not ds:
            ds = eval_svc.create_dataset(
                name=dataset_name,
                description="Standard HR and IT compliance evaluation dataset for Enterprise Document Intelligence.",
            )
            for item in BENCHMARK_QUESTIONS:
                eval_svc.add_question(
                    dataset_id=str(ds.id),
                    question=item["question"],
                    ground_truth=item["ground_truth"],
                )
            print(f"Created evaluation dataset '{dataset_name}' with {len(BENCHMARK_QUESTIONS)} questions.")
        else:
            print(f"Using existing dataset '{dataset_name}' ({len(ds.questions)} questions).")

        # 2. Run evaluation
        print("\nExecuting evaluation run...")
        run_record = await eval_svc.run_evaluation(
            dataset_id=str(ds.id),
            run_name="Local Automated Benchmark",
            retrieval_method="hybrid",
            top_k=5,
        )

        print("\n" + "=" * 60)
        print("EVALUATION RESULTS SUMMARY")
        print("=" * 60)
        metrics = run_record.metrics or {}
        for k, v in metrics.items():
            print(f"  {k:<25}: {v}")
        print("=" * 60)

    finally:
        db.close()


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()

from av_portfolio.definitions import defs

if __name__ == "__main__":
    print("🚀 Starting AV Portfolio KPI Pipeline Demo...")
    result = defs.get_implicit_global_asset_job_def().execute_in_process()
    if result.success:
        print("\n✅ Pipeline completed successfully!")
    else:
        print("\n❌ Pipeline failed.")

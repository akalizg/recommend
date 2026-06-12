from pyspark.sql import SparkSession


spark = SparkSession.builder.appName("RecipeRecSparkSmoke").getOrCreate()
try:
    sc = spark.sparkContext
    print("Spark connection OK")
    print(f"spark_version={spark.version}")
    print(f"master={sc.master}")
    print(f"app_id={sc.applicationId}")
    print(f"default_parallelism={sc.defaultParallelism}")
    print(f"web_ui={sc.uiWebUrl}")
    print(f"test_count={spark.range(0, 1000).repartition(6).count()}")
finally:
    spark.stop()


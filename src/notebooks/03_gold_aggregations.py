# Databricks notebook source
# MAGIC %md
# MAGIC # 03 - Gold Aggregations
# MAGIC Creates business-level aggregates for reporting and Genie Spaces.

# COMMAND ----------

dbutils.widgets.text("catalog", "hp_dev", "Catalog")
dbutils.widgets.text("schema", "hp_pp_schema", "Schema")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

spark.sql(f"USE CATALOG {catalog}")
spark.sql(f"USE SCHEMA {schema}")

# COMMAND ----------

from pyspark.sql import functions as F

df_silver = spark.table("silver_orders")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Daily revenue summary

# COMMAND ----------

df_daily_revenue = (
    df_silver
    .groupBy("order_date")
    .agg(
        F.count("order_id").alias("total_orders"),
        F.sum("total_amount").alias("daily_revenue"),
        F.avg("total_amount").alias("avg_order_value"),
        F.countDistinct("customer_id").alias("unique_customers"),
    )
    .orderBy("order_date")
)

df_daily_revenue.write.format("delta") \
    .mode("overwrite") \
    .saveAsTable("gold_daily_revenue")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Product category summary

# COMMAND ----------

df_category_summary = (
    df_silver
    .groupBy("product_category")
    .agg(
        F.count("order_id").alias("total_orders"),
        F.sum("total_amount").alias("total_revenue"),
        F.sum("quantity").alias("total_units_sold"),
        F.avg("unit_price").alias("avg_unit_price"),
    )
    .orderBy(F.desc("total_revenue"))
)

df_category_summary.write.format("delta") \
    .mode("overwrite") \
    .saveAsTable("gold_category_summary")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Customer lifetime value

# COMMAND ----------

df_customer_ltv = (
    df_silver
    .groupBy("customer_id")
    .agg(
        F.count("order_id").alias("total_orders"),
        F.sum("total_amount").alias("lifetime_value"),
        F.min("order_date").alias("first_order_date"),
        F.max("order_date").alias("last_order_date"),
    )
    .withColumn("avg_order_value", F.col("lifetime_value") / F.col("total_orders"))
    .orderBy(F.desc("lifetime_value"))
)

df_customer_ltv.write.format("delta") \
    .mode("overwrite") \
    .saveAsTable("gold_customer_ltv")

# COMMAND ----------

print("Gold tables created:")
for table in ["gold_daily_revenue", "gold_category_summary", "gold_customer_ltv"]:
    count = spark.table(table).count()
    print(f"  {catalog}.{schema}.{table}: {count} rows")

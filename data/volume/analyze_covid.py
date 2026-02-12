import pandas as pd

# Load the CSV file
df = pd.read_csv('countries-aggregated.csv')

# Display basic info
print("Data shape:", df.shape)
print("\nColumns:", df.columns.tolist())
print("\nFirst few rows:")
print(df.head())

# Since this is time-series data with cumulative confirmed cases,
# we take the maximum confirmed value per country
country_totals = df.groupby('Country')['Confirmed'].max().reset_index()

# Sort by confirmed cases in descending order
top_5 = country_totals.sort_values('Confirmed', ascending=False).head(5)

print("\n" + "="*50)
print("TOP 5 COUNTRIES BY TOTAL CONFIRMED COVID-19 CASES")
print("="*50)
for i, row in top_5.iterrows():
    print(f"{row['Country']}: {row['Confirmed']:,} cases")

print("\n" + "="*50)
print("Top 5 as DataFrame:")
print(top_5.to_string(index=False))

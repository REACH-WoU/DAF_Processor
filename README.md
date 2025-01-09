### **App Description**

This app is meant to automate the creation of analysis frequency tables.  
It requires the user to provide the dataframe, the Kobo tool, and the filled-out DAF file. While slower than the script run on the local machine, this app allows independent data exploration.  
It has all the regular capabilities of Tabular Analysis V4, including filters, joins, and calculations.

### **DAF Requirements**

The app requires the regular Kobo tool and the dataframe with all the relevant variables. The app does not transform the dataframe in any way, so if the user wants to produce a table with a non-existing variable, the app will produce an error.  
The app requires the V4 version of the DAP tool that has two sheets - `main` and `filter`.  

The `main` sheet should have the following columns:  

| **ID**         | **variable**              | **variable_label**                                           | **calculation**                            | **func**                                                              | **admin**                                  | **disaggregations**                              | **disaggregations_label**                | **join**                                         |
|-----------------|---------------------------|-------------------------------------------------------------|--------------------------------------------|------------------------------------------------------------------------|---------------------------------------------|-------------------------------------------------|------------------------------------------|--------------------------------------------------|
| Row index       | The name of the variable | The label of your variable, what did you ask the respondent? | Supports two functions `include_na` and `add_total`. | Whether the variable should be disaggregated as a frequency or as a weighted mean | The admin unit to be used for the disaggregation | What is the disaggregation variable you want to use for your variable? | A nice label of your disaggregation column | The ID of the parent row of the dependent table |


The second page of the DAF file is the `filter` page and allows the user to perform three types of operations on the data:  

- **Numeric filter** (e.g., `variable > 5`)  
- **Character filter** (e.g., `variable == Yes`) **No quotation marks are needed**  
- **Variable filter** (e.g., `variable > variable2`) **Be careful when using this**  

The filter table should have the following form:  


| **ID**         | **variable**           | **operation**         | **filter**     |
|-----------------|------------------------|-----------------------|----------------|
| The id of the variable in the main sheet | The filtering variable | Filtering operation | Filter         |


---

### **How to Use the App**

1. Upload your data, Kobo tool, and DAF file into the relevant uploader windows in the **Processor** tab of the app.  
2. If you want to perform weighted analysis:  
   - Click the checkbox under the question about weights and select the weight variable from your data.  
   - If not, leave the checkbox unchecked.  
3. To run a significance check (variance analysis) or add conditional formatting (color coding percentages and numeric statistics to quickly identify unusual entries):  
   - Check the relevant checkboxes.  
4. Click the **Process** button.  

The processing should take a few minutes depending on the size of your dataset and DAF. You will receive notifications updating you on the progress.  
Once processing is complete (you will see a notification and the top of the page will stop flashing), click **Download** to retrieve your results.

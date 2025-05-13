import pandas as pd
from pandas.api.types import is_numeric_dtype
from datetime import datetime
from copy import deepcopy
import re
import io
import zipfile
# Read the functions
from www.src.functions import *


from shiny import *

import time



app_ui = ui.page_fluid(
    ui.HTML(
        f'<a style="padding-left:10px;" class="app-title" href= "https://www.reach-initiative.org/" target="_blank"><img src="www/reach.jpg" height = "50"></a><span class="app-description" style="font-size: 16px; color: #FFFFFF"><strong>DAF Processor</strong></span>'
    ),
    ui.HTML('<br>'),
    ui.navset_tab(
        ui.nav_panel('Read Me',
                     ui.HTML('''
    <h3><b>App Description</b></h3>
    <br>
    <h4>This app is meant to automate the creation of the analysis frequency tables. 
    It requires the user to provide the dataframe, the Kobo tool, and the filled-out DAF file. While slower than the script run on the local machine, this app allows independent data exploration. 
    It has all of the regular capabilities of tabular analysis V4 including filters, joins, and calculations.</h4>
    <h3><b>DAF requirements</b></h3>
    <h4>The app requires the regular Kobo tool and the dataframe with all of the relevant variables. The app does not transform the dataframe in any way, so if the user wants to produce a table with a non-existing variable, the app will produce an error. 
    The app requires the V4 version of the DAP tool that has two sheets - main and filter.<br>The main sheet should have the following columns:</h4>
'''),
                     ui.output_data_frame("output_table1"),
                     ui.HTML('''
    <h4>The second page of the DAF file is the filter page and allows the user to perform 3 types of operations on the data:</h4>
    <h4> - Numeric filter (e.g. variable > 5)</h4>
    <h4> - Character filter (e.g. variable == Yes) <b>No quotation marks are needed</b></h4>
    <h4> - Variable filter (e.g. variable > variable2) <b>Be careful when using this</b></h4>
    <br>
    <h4> The filter table should have the following form:</h4>
'''),
                     ui.output_data_frame("output_table2"),
                     ui.HTML('''
    <h3><b>How to use the app</b></h3>
    <h4>Upload your data, kobo tool, and DAF file into the relevant uploader windows in the <b>Processor</b> tab of the app.
    If you want to perform weighted analysis, click the checkbox under the question about weights and select the weight variable from your data; if not, do not click the checkbox. 
    If you want to run a significance check - variance analysis that will check if the variables in the row of your DAF are significantly associated 
    or add conditional formating to your file - color coding the percentages and numeric statistics to quickly find unusual entries, check the relevant checkboxes.
    After this, click the Process button.
    The processing should take a few minutes depending on the size of your dataset and DAF. You will get notifications updating you on the progress.
    Once that is done (you will see a notification and the top of the page will stop flashing), you can click download.</h4>
''')
        ),
        ui.nav_panel('The processor',
                ui.layout_sidebar(
                    ui.sidebar(
                        'Upload your files',
                        ui.input_file("file_daf", "Choose a DAF to upload:", accept=[".xlsx"]),
                        ui.input_file("file_tool", "Upload your kobo tool", accept=[".xlsx"]),
                        ui.input_file("file_data", "Upload your dataframe", accept=[".xlsx"]),
                        ui.input_checkbox('checkbox','Does your data have weights?'),
                        ui.panel_conditional(
                            'input.checkbox',
                            ui.input_selectize('weight_column', 
                                            'Select the weight column from your dataframe',
                                            choices = [],
                                            multiple=False
                                            )
                            ),
                        ui.input_checkbox('checkbox_sign','Would you like to run a significance check on your data?'),
                        ui.input_checkbox('checkbox_form','Would you like to add conditional formatting to your tables?'),
                        ui.input_checkbox('checkbox_moe','Would you like to add margin of error for numeric statistics?'),

                        ui.download_button("download_data", "Process your request"),
                        ui.HTML('<br>'),
                        ui.HTML('<br>'),
                        width = 1000,
                        open = 'always'
                        )
                    )
                )
        )
    )

def server(input:Inputs, output: Outputs, session:Session):
    
    @render.data_frame
    def output_table1():
        data = {
            'ID': ['Row index'],
            'variable': ['The name of the variable'],
            'variable_label': ['The label of your variable, what did you ask the respondent?'],
            'calculation': ['Supports two functions include_na and add_total.'],
            'func': ['Whether the variable should be disaggregated as a frequency or as a weighted mean	'],
            'admin': ['The admin unit to be used for the disaggregation'],
            'disaggregations': ['What is the disaggregation variable you want to use for your variable?'],
            'disaggregations_label': ['A nice label of your disaggregation column'],
            'join': ['The ID of the parent row of the dependent table']
            }
        df = pd.DataFrame(data)
        return render.DataTable(df,
                                width="100%",
                                height="550",
                                filters=False
                                )

    @render.data_frame
    def output_table2():
        data = {
            'ID': ['The id of the variable in the main sheet'],
            'variable': ['The filtering variable'],
            'operation': ['Filtering operation'],
            'filter': ['Filter']
            }
        df = pd.DataFrame(data)
        return render.DataTable(df,
                                width="100%",
                                height="550",
                                filters=False
                                )

    # set up the reactives
    data_file = reactive.value(None)
    data_sheets = reactive.value(None)
    daf_file_main = reactive.value(None)
    daf_file_filter = reactive.value(None)
    label_colname = reactive.value(None)
    tool_survey_file = reactive.value(None)
    tool_choices_file = reactive.value(None)
    error_message = reactive.value(None)
    weighting_column_input = reactive.value(None)
    
    # set up output tables
    perc_tbl= reactive.value(None)
    count_w_tbl= reactive.value(None)
    count_tbl= reactive.value(None)
    conc_tbl= reactive.value(None)
    conc_key_tbl= reactive.value(None)
    
    # check the basic data structure and get the weight column
    @reactive.effect
    @reactive.event(input.file_data)
    def load_data():
        sheets, small_data = get_sheets_small_data(input.file_data()[0]["datapath"])
        data_sheets.set(sheets)
        matcher = re.compile('weight')
        weight_list = list(filter(matcher.match,small_data[sheets[0]].columns))
        weight_list = weight_list+[None]
        ui.update_selectize('weight_column', choices=weight_list, selected=None)

    # load the tool and check the sheet names. If all good, set the label colname reactive
    @reactive.effect
    @reactive.event(input.file_tool)
    def load_tool_check():
        sheets_dat, small_data = get_sheets_small_data(input.file_tool()[0]["datapath"])
        err_msg = error_message.get()
        if set(['survey','choices']).issubset(set(sheets_dat)):
            tool_s = pd.read_excel(input.file_tool()[0]['datapath'], sheet_name= 'survey')
            tool_c = pd.read_excel(input.file_tool()[0]['datapath'], sheet_name= 'choices')
            matcher = re.compile(r'label.*english',re.IGNORECASE)
            tool_s_label = list(filter(matcher.match,tool_s.columns))
            tool_c_label = list(filter(matcher.match,tool_c.columns))
            

            if tool_s_label ==tool_c_label:
                label_colname.set(tool_s_label)
            else:
                if err_msg == None :
                    error_message.set('Error: english label columns do not match in the kobo survey/choices sheets')
                else:
                    error_message.set(err_msg+' '+'Error: english label columns do not match in the kobo survey/choices sheets')
        else:
            if err_msg is None:
                error_message.set('Error: missing survey or choices sheet in the kobo tool file')
            else:
                error_message.set(err_msg+' '+'Error: english label columns do not match in the kobo survey/choices sheets')

    # load the DAF and check if for issues
    @reactive.effect
    @reactive.event(input.file_daf)
    def load_daf_file():
        sheets_daf, small_data = get_sheets_small_data(input.file_daf()[0]["datapath"])
        if set(['main','filter']).issubset(set(sheets_daf)):
            daf = pd.read_excel(input.file_daf()[0]['datapath'], sheet_name="main")
            colnames_daf = set(['ID','variable','variable_label',
                    'calculation','func','admin','disaggregations','disaggregations_label',
                    'join'])
            if colnames_daf.issubset(daf.columns):
                # remove spaces
                for column in ['variable','admin','calculation','func','disaggregations']:
                    daf[column] = daf[column].apply(lambda x: x.strip() if isinstance(x, str) else x)
                # check if any of the variables are duplicated with their disaggregations
                if any(daf['variable']==daf['disaggregations']):
                    problematic_ids_str = ', '.join(str(id) for id in daf.loc[daf['variable'] == daf['disaggregations'], 'ID'])
                    if error_message.get() != None:
                        msg = error_message.get()
                        
                        error_message.set(msg + ' '+f'Variable and disaggregation are duplicated, problematic IDs: ' + \
                            problematic_ids_str)
                    else:
                        error_message.set(f'Variable and disaggregation are duplicated, problematic IDs: ' + \
                            problematic_ids_str)
                        
                if any(daf['variable']==daf['admin']):
                    problematic_ids_str = ', '.join(str(id) for id in daf.loc[daf['variable'] == daf['admin'], 'ID'])
                    if error_message.get() != None:
                        msg = error_message.get()
                        
                        error_message.set(msg + ' '+f'Variable and admin are duplicated, problematic IDs: ' + \
                            problematic_ids_str)
                    else:
                        error_message.set(f'Variable and admin are duplicated, problematic IDs: ' + \
                            problematic_ids_str)
                        
                
                if any(daf['admin']==daf['disaggregations']):
                    problematic_ids_str = ', '.join(str(id) for id in daf.loc[daf['admin'] == daf['disaggregations'], 'ID'])
                    if error_message.get() != None:
                        msg = error_message.get()
                        
                        error_message.set(msg + ' '+f'Admin and disaggregation are duplicated, problematic IDs: ' + \
                            problematic_ids_str)
                    else:
                        error_message.set(f'Admin and disaggregation are duplicated, problematic IDs: ' + \
                            problematic_ids_str)
                        
                # check for the functions
                wrong_functions = set(daf['func'])-{'mean','numeric','select_one','select_multiple','freq'}
                if len(wrong_functions)>0:
                    if error_message.get() != None:
                        msg = error_message.get()
                        error_message.set(msg + ' '+f'Wrong functions entered: '+str(wrong_functions)+'. Please fix your function entries')
                    else:
                        error_message.set(f'Wrong functions entered: '+str(wrong_functions)+'. Please fix your function entries')
                
                # check for ID duplicates
                IDs = daf['ID'].duplicated()
                if any(IDs):
                    if error_message.get() != None:
                        msg = error_message.get()
                        error_message.set(msg + ' '+'Duplicate IDs in the ID column of the DAF')
                    else:
                        error_message.set('Duplicate IDs in the ID column of the DAF')
                
                # if after all of this we're good. assign the daf reactive
                daf_file_main.set(daf)
            else:
                error_message.set(f'Missing one or more columns from the DAF file main sheet:'+
                                  ', '.join(colnames_daf.difference(daf.columns)))
            
            # Check the filter sheer
            filter_daf = pd.read_excel(input.file_daf()[0]['datapath'], sheet_name="filter")
            colnames_daf_filter = set(['ID','variable','operation','value'])
            if colnames_daf_filter.issubset(set(filter_daf.columns)):
                daf_file_filter.set(filter_daf)
            else:
                error_message.set(f'Missing one or more columns from the DAF file filter sheet:'+
                                  ', '.join(colnames_daf_filter.difference(filter_daf.columns)))
            
        else:
            error_message.set('Missing one of the following sheets for DAF file: main, filter')

    # get the weighting column if present
    @reactive.effect
    @reactive.event(input.weight_column)
    def weighting_definition():
        weighting_column_input.set(input.weight_column())



    @render.download()
    def download_data():
        
        if input.checkbox_sign():
            check_signfic = True
        else:
            check_signfic = False
            
        if input.checkbox_form():
            check_formatting = True
        else:
            check_formatting = False

        if input.checkbox_moe():
            add_moe = True
        else:
            add_moe = False
                    
        start_time = time.time()
        if all([input.file_tool, input.file_data, input.file_daf]):

            if error_message.get() != None:
                modal_error = ui.modal(error_message.get(),
                                       title='Error',
                                       easy_close=True,
                                       footer=None)
                ui.modal_show(modal_error)
            else:
                ui.notification_show("Processing your data", duration=20, type="message")
                
                data_file.set(pd.read_excel(input.file_data()[0]['datapath'],sheet_name=data_sheets.get()))
                tool_choices_file.set(load_tool_choices(input.file_tool()[0]['datapath'], label_colname = label_colname.get()[0]))
                tool_survey_file.set(load_tool_survey(input.file_tool()[0]['datapath'], label_colname = label_colname.get()[0]))
                
                # get the usual names for the inputs
                print('Read the files')
                data = data_file.get()
                sheets = data_sheets.get()
                
                tool_choices = tool_choices_file.get()
                tool_survey = tool_survey_file.get()
                
                daf = daf_file_main.get()
                filter_daf = daf_file_filter.get()
                
                weighting_column = weighting_column_input.get()
                
                label_column = label_colname.get()[0]
                
                if weighting_column =='':
                    weighting_column=None
                

                # pre_process data and test for more errors
                print('Pre_process the files')

                for sheet_name in sheets:
                    data[sheet_name]['overall'] =' Overall'
                    data[sheet_name]['Overall'] =' Overall'
                                
                # add a sheet name to the daf
                names_data= pd.DataFrame()
                for sheet_name in sheets:
                    # get all the names in your dataframe list
                    variable_names = data[sheet_name].columns
                    # create a lil dataframe of all variables in all sheets
                    dat = {'variable' : variable_names, 'datasheet' :sheet_name}
                    dat = pd.DataFrame(dat)
                    names_data = pd.concat([names_data, dat], ignore_index=True)
                    
                names_data = names_data.reset_index(drop=True)
                # check if we have any duplicates
                duplicates_frame = names_data.duplicated(subset='variable', keep=False)
                if duplicates_frame[duplicates_frame==True].shape[0] >0:
                # get non duplicate entries
                    names_data_non_dupl = names_data[~duplicates_frame]
                    deduplicated_frame = pd.DataFrame()
                    # run a loop for all duplicated names
                    for i in names_data.loc[duplicates_frame,'variable'].unique():
                        temp_names =  names_data[names_data['variable']==i]
                        temp_names = temp_names.reset_index(drop=True)
                        # if the variable is present in main sheet, keep only that version
                        if temp_names['datasheet'].isin(['main']).any():
                            temp_names = temp_names[temp_names['datasheet']=='main']
                        # else, keep whatever is available on the first row
                        else:
                            temp_names = temp_names[:1]
                        deduplicated_frame=pd.concat([deduplicated_frame, temp_names])
                    names_data = pd.concat([names_data_non_dupl,deduplicated_frame])

                
                # and now we have our DAF
                daf_merged = daf.merge(names_data,on='variable', how = 'left')
                
                if any(daf_merged['datasheet'].isna()):
                    error_message_base = 'Missing the following variables from the dataframe: '+', '.join(daf_merged[daf_merged['datasheet'].isna()]['variable'].unique().astype('str'))
                else:
                    error_message_base = None
                 
                if error_message_base is not None:
                    modal_1 = ui.modal(
                        error_message_base,
                        title='Error',
                        easy_close=True,
                        footer=False
                    )
                    ui.modal_show(modal_1)
                else:
                    try:    
                        daf_merged = check_daf_consistency(daf_merged, data, sheets, resolve=False)
                    
                        daf_numeric = daf_merged[daf_merged['func'].isin(['numeric', 'mean'])]
                        if daf_numeric.shape[0]>0:
                            for i, daf_row in daf_numeric.iterrows():
                                res  = is_numeric_dtype(data[daf_row['datasheet']][daf_row['variable']])
                                if res == False:
                                    raise ValueError(f"Variable {daf_row['variable']} from datasheet {daf_row['datasheet']} is not numeric, but you want to apply a mean function to it in your DAF")
                        #Checking your filter page and building the filter dictionary
                        
                        if filter_daf.shape[0]>0:
                            
                            for col in filter_daf.columns:
                                if col != 'ID':
                                    filter_daf[col] = filter_daf[col].str.replace(' ', '')
                                    filter_daf[col] = filter_daf[col].str.replace("'", '')
                                    
                            check_daf_filter(daf =daf_merged, data = data,filter_daf=filter_daf, tool_survey=tool_survey)
                            # Create filter dictionary object 
                            filter_daf_full = filter_daf.merge(daf_merged[['ID','datasheet']], on = 'ID',how = 'left')

                            filter_dict = {}
                            # Iterate over DataFrame rows
                            for index, row in filter_daf_full.iterrows():
                                # If the value is another variable, don't use the string bit for it
                                if isinstance(row['value'], str) and row['value'] in data[row['datasheet']].columns:
                                    condition_str = f"(data['{row['datasheet']}']['{row['variable']}'] {row['operation']} data['{row['datasheet']}']['{row['value']}'])"
                                # If the value is a string and is equal
                                elif isinstance(row['value'], str) and row['operation']=='==':
                                    condition_str = f"(data['{row['datasheet']}']['{row['variable']}'].astype(str).str.contains('{row['value']}', regex=True))"
                                # If the value is a string and is not equal
                                elif isinstance(row['value'], str) and row['operation']=='!=':
                                    condition_str = f"(~data['{row['datasheet']}']['{row['variable']}'].astype(str).str.contains('{row['value']}', regex=True))"
                                # Otherwise just keep as is
                                else:
                                    condition_str = f"(data['{row['datasheet']}']['{row['variable']}'] {row['operation']} {row['value']})"
                                if row['ID'] in filter_dict:
                                    filter_dict[row['ID']].append(condition_str)
                                else:
                                    filter_dict[row['ID']] = [condition_str]

                            # Join the similar conditions with '&'
                            for key, value in filter_dict.items():
                                filter_dict[key] = ' & '.join(value)
                            filter_dict = {key: f'{value}]' for key, value in filter_dict.items()}
                        else:
                            filter_dict = {}
                        
                        
                        if weighting_column != None:
                            for sheet_name in sheets:
                                if data[sheet_name][weighting_column].isnull().sum().any():
                                    raise ValueError(f"The weight column in sheet {sheet_name} contains NAs please fix this")
                        
                        daf_final = daf_merged.merge(tool_survey[['name','q.type']], left_on = 'variable',right_on = 'name', how='left')
                        daf_final['q.type']=daf_final['q.type'].fillna('select_one') 
                        
                        print('Building your tables')
                        # analyse the data here
                        disaggregations_full = disaggregation_creator(daf_final, data,filter_dict, tool_choices, tool_survey, label_colname = label_column, check_significance= check_signfic, weight_column = weighting_column, add_moe=add_moe)
                        print('building the outputs')
                        disaggregations_orig = deepcopy(disaggregations_full) # analysis key table

                        for element in disaggregations_full:
                            if isinstance(element[0], pd.DataFrame):  
                                if all(column in element[0].columns for column in element[0].columns if column.endswith('orig')):
                                    element[0].drop(columns=[col for col in  element[0].columns if col.endswith('orig')], inplace=True)

                        disaggregations_perc = deepcopy(disaggregations_full) # percentage table
                        disaggregations_count = deepcopy(disaggregations_full) # count table
                        disaggregations_count_w = deepcopy(disaggregations_full) # weighted count table

                        # remove counts prom perc table
                        for element in disaggregations_perc:
                            if isinstance(element[0], pd.DataFrame):
                                
                                # Drop each column if it exists in the DataFrame
                                if "min" not in element[0].columns:
                                    columns_to_drop = ['general_count', 'weighted_count', 'unweighted_count']
                                    for column in columns_to_drop:
                                        if column in element[0].columns:
                                            element[0].drop(columns=column, inplace=True)
                                    element[0].rename(columns={'general_count_uw': 'general_count'}, inplace=True)
                                else:
                                    columns_to_drop = ['category_count', 'weighted_count', 'general_count_uw']
                                    for column in columns_to_drop:
                                        if column in element[0].columns:
                                            element[0].drop(columns=column, inplace=True)
                                    element[0].rename(columns={'unweighted_count': 'general_count'}, inplace=True)


                        # remove perc columns from weighted count table
                        for element in disaggregations_count_w:
                            if isinstance(element[0], pd.DataFrame):  
                                columns_to_drop = ['perc', 'unweighted_count']
                                for column in columns_to_drop:
                                    if column in element[0].columns:
                                        element[0].drop(columns=column, inplace=True)
                                element[0].rename(columns={'weighted_count': 'category_count'}, inplace=True)
                                
                        # remove perc columns from unweighted count table
                        for element in disaggregations_count:
                            if isinstance(element[0], pd.DataFrame):  
                                columns_to_drop = ['perc', 'weighted_count','general_count']
                                for column in columns_to_drop:
                                    if column in element[0].columns:
                                        element[0].drop(columns=column, inplace=True)
                                element[0].rename(columns={'unweighted_count': 'category_count'}, inplace=True)
                                if "min" not in element[0].columns:
                                    element[0].rename(columns={'general_count_uw': 'general_count'}, inplace=True)


                        # Get the columns for Analysis key table 
                        concatenated_df_orig = pd.concat([tpl[0] for tpl in disaggregations_orig], ignore_index = True)
                        if 'disaggregations_category_1' in concatenated_df_orig.columns:
                            concatenated_df_orig = concatenated_df_orig[(concatenated_df_orig['admin'] != 'Total') & (concatenated_df_orig['disaggregations_category_1'] != 'Total')]
                        else:
                            concatenated_df_orig = concatenated_df_orig[(concatenated_df_orig['admin'] != 'Total')]
    
                        disagg_columns_og = [col for col in concatenated_df_orig.columns if col.startswith('disaggregations') and not col.endswith('orig')]
                        ls_orig = ['admin','admin_category','option', 'variable']+disagg_columns_og

                        for column in ls_orig:
                            if column in concatenated_df_orig.columns:
                                if column+'_orig' not in concatenated_df_orig.columns:
                                    concatenated_df_orig[column+'_orig'] = concatenated_df_orig[column]
                                concatenated_df_orig[column+'_orig'] = concatenated_df_orig[column+'_orig'].infer_objects(copy=False).fillna(concatenated_df_orig[column])


                        concatenated_df_orig = concatenated_df_orig.merge(daf_final[['ID','q.type']], on='ID', how='left')

                        concatenated_df_orig['key'] = concatenated_df_orig.apply(key_creator, axis=1)

                        if 'mean' in concatenated_df_orig.columns:
                            if 'perc' in concatenated_df_orig.columns:
                                concatenated_df_orig['perc'] = concatenated_df_orig['perc'].fillna(concatenated_df_orig['mean'])
                            else:
                                concatenated_df_orig['perc'] = concatenated_df_orig['mean']

                        concatenated_df_orig=concatenated_df_orig[['key','perc']]

                        # prepare dashboard inputs 
                        concatenated_df = pd.concat([tpl[0] for tpl in disaggregations_perc], ignore_index = True)
                        if 'disaggregations_category_1' in concatenated_df.columns:
                            concatenated_df = concatenated_df[(concatenated_df['admin'] != 'Total') & (concatenated_df['disaggregations_category_1'] != 'Total')]
                        else:
                            concatenated_df = concatenated_df[(concatenated_df['admin'] != 'Total')]


                        disagg_columns = [col for col in concatenated_df.columns if col.startswith('disaggregations')]
                        concatenated_df.loc[:,disagg_columns] = concatenated_df[disagg_columns].fillna(' Overall')

                        
                        
                        # Join tables if needed
                        print('Joining tables if such was specified')
                        disaggregations_perc_new = disaggregations_perc.copy()
                        disaggregations_count_new  = disaggregations_count.copy()
                        disaggregations_count_w_new  = disaggregations_count_w.copy()

                        disaggregations_perc_new_for_group = disaggregations_perc_new.copy()

                        # check if any joining is needed
                        for data_frame in [disaggregations_perc_new,disaggregations_count_new,disaggregations_count_w_new]:
                            # check if any joining is needed
                            if pd.notna(daf_final['join']).any():

                                # get other children here
                                child_rows = daf_final[pd.notna(daf_final['join'])]

                                if any(child_rows['ID'].isin(child_rows['join'])):
                                    raise ValueError('Some of the join tables are related to eachother outside of their relationship with the parent row. Please fix this')
                                

                                for index, child_row in child_rows.iterrows():
                                    child_index = child_row['ID']
                                    
                                    if child_index not in daf_final['ID'].values:
                                        raise ValueError(f'The specified parent index in join column for child row ID = {child_index} doesnt exist in the DAF file')
                                    
                                    parent_row = daf_final[daf_final['ID'].isin(child_row[['join']])]
                                    parent_index = parent_row.iloc[0]['ID']


                                    # check that the rows are idential
                                    parent_check = parent_row[['disaggregations','func','calculation','admin','q.type']].reset_index(drop=True)
                                    child_check = child_row.to_frame().transpose()[['disaggregations','func','calculation','admin','q.type']].reset_index(drop=True)

                                    # transform None to be of the same type
                                    parent_check = parent_check.infer_objects(copy=False).fillna('I am empty')
                                    child_check = child_check.infer_objects(copy=False).fillna('I am empty')
                                    
                                    check_result = child_check.equals(parent_check)
                                    if not check_result:
                                        raise ValueError(f"Joined rows (parent: {str(parent_row['ID'].values)} and child: {str(child_row['ID'])}) are not identical in terms of admin, calculations, function and disaggregations")
                                    # get the data and dataframe indeces of parents and children
                                    child_tupple = [(i,tup) for i, tup in enumerate(data_frame) if tup[1] == child_index]
                                    parent_tupple = [(i, tup) for i, tup in enumerate(data_frame) if tup[1] == parent_index]

                                    child_tupple_data = child_tupple[0][1][0].copy()
                                    child_tupple_index = child_tupple[0][0]
                                    parent_tupple_data = parent_tupple[0][1][0].copy()
                                    parent_tupple_index = parent_tupple[0][0]
                                    # rename the data so that they are readable
                                    if parent_tupple_data['variable'][0] == child_tupple_data['variable'][0]:
                                        var_parent = parent_tupple_data['variable'][0] + '_' +str(parent_tupple_data['ID'][0])
                                        var_child = child_tupple_data['variable'][0] + '_' + str(child_tupple_data['ID'][0])
                                        warnings.warn("Some of the rows you're joining have the same variable label. This won't look nice")
                                    else:
                                        var_parent = parent_tupple_data['variable'][0] 
                                        var_child = child_tupple_data['variable'][0] 
                                    
                                    varnames = [var_parent,var_child]
                                    dataframes =[parent_tupple_data, child_tupple_data]

                                    for var, dataframe in  zip(varnames, dataframes):
                                        rename_dict = {'mean': 'mean_'+var,'moe_mean': 'moe_mean_'+var,'median': 'median_'+var ,'moe_median': 'moe_median_'+var, 'count': 'count_'+var, 
                                                    'weighted_count': 'weighted_count_'+var,'unweighted_count': 'unweighted_count_'+var,
                                                    'category_count': 'category_count_'+var, 'general_count': 'general_count_'+var,
                                                    'perc': 'perc_'+var,'min': 'min_'+var, 'max': 'max_'+var}

                                        for old_name, new_name in rename_dict.items():
                                            if old_name in dataframe.columns:
                                                dataframe.rename(columns={old_name: new_name},inplace=True)


                                    # get the lists of columns to keep and merge
                                    columns_to_merge = [item for item in parent_tupple_data.columns if 'disaggregations' in item  or 'admin' in item]
                                    if 'option' in  parent_tupple_data.columns:
                                        columns_to_merge=columns_to_merge+['option']
                                        
                                    columns_to_keep = columns_to_merge+ list(rename_dict.values())

                                    parent_tupple_data= parent_tupple_data.merge(
                                        child_tupple_data[child_tupple_data.columns.intersection(columns_to_keep)], 
                                        on = columns_to_merge,how='left')


                                    parent_index_f = parent_tupple[0][1][1]

                                    parent_label_f = str(parent_tupple[0][1][2])
                                        
                                    if str(child_tupple[0][1][3]) != '':
                                        parent_sig_f = str(child_tupple[0][1][3])+' & '+ str(parent_tupple[0][1][3])
                                    else:
                                        parent_sig_f = ''

                                    if "full_count" in parent_tupple_data.columns:
                                        parent_tupple_data = parent_tupple_data.drop(columns=['full_count'])
                                    if any([x.startswith(('general_')) for x in parent_tupple_data.columns]):
                                        parent_tupple_data['general_count_max'] = parent_tupple_data.filter(regex='^general_').max(axis=1)
                                    else:
                                        parent_tupple_data['category_count_max'] = parent_tupple_data.filter(regex='^category_').max(axis=1)
                                    if 'comment' in daf_final.columns:
                                        if daf_final.loc[daf_final['ID'] == parent_index_f, 'comment'].iloc[0] == "general_count_max":
                                            parent_tupple_data = parent_tupple_data.loc[:, ~parent_tupple_data.columns.str.startswith('general_') | (parent_tupple_data.columns == 'general_count_max')]
                                        if daf_final.loc[daf_final['ID'] == parent_index_f, 'comment'].iloc[0] == "category_count_max":
                                            parent_tupple_data = parent_tupple_data.loc[:, ~parent_tupple_data.columns.str.startswith('category_') | (parent_tupple_data.columns == 'category_count_max')]
                                    count_cols_to_drop = [col for col in parent_tupple_data.columns
                                                if col.startswith('general_count_') and col != 'general_count_max']
                                    count_cols_to_drop += [col for col in parent_tupple_data.columns
                                                if col.startswith('category_count_') and col != 'category_count_max']
                                    parent_tupple_data = parent_tupple_data.drop(columns=count_cols_to_drop)
                                    new_list = (parent_tupple_data, parent_index_f, parent_label_f,parent_sig_f)
                                    data_frame[parent_tupple_index] = new_list
                                    del data_frame[child_tupple_index]

                        
                        disaggregations_perc_new = sorted(disaggregations_perc_new, key=lambda x: x[1])
                        disaggregations_count_w_new = sorted(disaggregations_count_w_new, key=lambda x: x[1])
                        disaggregations_count_new = sorted(disaggregations_count_new, key=lambda x: x[1])

                        # print(disaggregations_count_new[0][0].columns)
                        
                        perc_tbl.set(disaggregations_perc_new)
                        count_w_tbl.set(disaggregations_count_w_new)
                        count_tbl.set(disaggregations_count_new)
                        conc_tbl.set(concatenated_df)
                        conc_key_tbl.set(concatenated_df_orig)
                        # remove all modal windows
                        ui.notification_show("Finished processing", duration=5, type="message")
                        
                        # prepare the files for download
                        
                        disaggregations_perc_new = perc_tbl.get()
                        disaggregations_count_w = count_w_tbl.get()
                        disaggregations_count = count_tbl.get()
                        concatenated_df = conc_tbl.get()
                        concatenated_df_orig = conc_key_tbl.get()
                                                                
                        weighting_column = weighting_column_input.get()
                                
                        if weighting_column =='':
                            weighting_column=None
                        
                        
                        # write excel files
                        ui.notification_show("Writing your files", duration=20, type="message")
                        filename = 'request_file'+'_'+datetime.today().strftime('%Y_%m_%d')

                        filename_dash =filename+'_dashboard.xlsx'
                        filename_key = filename+'_analysis_key.xlsx'
                        filename_toc = filename+'_TOC.xlsx'
                        filename_toc_count = filename+'_TOC_count_unweighted.xlsx'
                        filename_toc_count_w =filename+'_TOC_count_weighted.xlsx'
                        filename_wide_toc = filename+'_wide_TOC.xlsx'
                        
                        # print(check_formatting)
                        # construct_result_table(disaggregations_perc_new, filename_toc,make_pivot_with_strata = False,
                        #                        color_cells=check_formatting,
                        #                        conditional_formating=check_formatting)
                        
                        # if weighting_column != None:
                        #     construct_result_table(disaggregations_count_w, filename_toc_count_w,make_pivot_with_strata = False,
                        #                        color_cells=check_formatting,
                        #                        conditional_formating=check_formatting)
                        # construct_result_table(disaggregations_count, filename_toc_count,make_pivot_with_strata = False,
                        #                        color_cells=check_formatting,
                        #                        conditional_formating=check_formatting)
                        # construct_result_table(disaggregations_perc_new, filename_wide_toc,make_pivot_with_strata = True,
                        #                        color_cells=check_formatting,
                        #                        conditional_formating=check_formatting)


                        tables = {
                            filename_dash: concatenated_df,
                            filename_key: concatenated_df_orig
                        }
                        
                        tables_for_function ={
                            filename_toc: disaggregations_perc_new,
                            filename_toc_count: disaggregations_count,
                            # filename_wide_toc: disaggregations_perc_new
                        }
                        
                        if weighting_column != None:
                            tables_for_function.update({filename_toc_count_w:disaggregations_count_w})

                        zip_path = 'tables.zip'

                        # Create a ZipFile object
                        with zipfile.ZipFile(zip_path, 'w') as zipf:
                            for filename, df in tables.items():
                                # Use an in-memory bytes buffer
                                buffer = io.BytesIO()
                                df.to_excel(buffer, index=False)
                                # Move to the beginning of the buffer
                                buffer.seek(0)
                                # Write buffer to zip file
                                zipf.writestr(filename, buffer.read())
                            
                            for filename_constr, df in tables_for_function.items():
                                buffer = io.BytesIO()
                                if 'wide' in filename_constr:
                                    construct_result_table(df, buffer,make_pivot_with_strata=True,
                                                           color_cells=check_formatting,
                                                           conditional_formating=check_formatting)
                                else:
                                    construct_result_table(df, buffer,make_pivot_with_strata=False,
                                                           color_cells=check_formatting,
                                                           conditional_formating=check_formatting)
                                buffer.seek(0)
                                zipf.writestr(filename_constr,buffer.read())
                            
                            filename = 'request_file'+'_'+datetime.today().strftime('%Y_%m_%d')

                            buffer = io.BytesIO()
                            grouped_filename = filename + "_grouped.xlsx"
                            construct_result_wide_table(disaggregations_perc_new_for_group, buffer)
                            buffer.seek(0)
                            zipf.writestr(grouped_filename, buffer.read())
                            
                            buffer = io.BytesIO()
                            grouped_filename_count = grouped_filename.split('.')[0] + "_count" + ".xlsx"
                            construct_count_wide_table(disaggregations_perc_new_for_group, buffer)
                            buffer.seek(0)
                            zipf.writestr(grouped_filename_count, buffer.read())
                                
                        print("--- %s seconds ---" % (time.time() - start_time))
                        
                        return zip_path

                            
                    except Exception as e:
                        modal_error_fin = ui.modal(str(e),
                                title = 'Error',
                                easy_close=True,
                                footer=None)
                        
                        ui.modal_remove()
                        ui.modal_show(modal_error_fin)
                        

app = App(app_ui, server, debug=True)
# app.run()
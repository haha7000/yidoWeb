import pandas as pd\

def ExcelToDf(excel_path):

    df = pd.read_excel(excel_path)
    df.columns = df.columns.get_level_values(0)
    
    # 컬럼명 변경
    df = df.rename(columns={'교환권번호': 'receiptNumber', '고객명': 'name'})

    return df

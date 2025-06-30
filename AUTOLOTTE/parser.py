import xml.etree.ElementTree as ET

class LotteParser:
    def __init__(self):
        # 지점 코드와 지점명 매핑
        self.store_mapping = {
            '901': '명동본점', '902': '월드타워', '90S': '코엑스',
            '908': '부산', '90G': '제주', '909': '김해공항',
            '905': '인천공항T1', '90L': '인천공항T2', '90C': '김포공항',
            901: '명동본점', 902: '월드타워', 908: '부산',
            909: '김해공항', 905: '인천공항T1'
        }
    
    def parse_sales_xml(self, xml_text):
        """XML 응답을 파싱하여 데이터 추출"""
        try:
            # XML 파일 저장 (디버깅용)
            with open('sales_response.xml', 'w', encoding='utf-8') as f:
                f.write(xml_text)
            print("📁 응답 XML을 sales_response.xml에 저장했습니다.")
            
            root = ET.fromstring(xml_text)
            ns = {'ns': 'http://www.nexacroplatform.com/platform/dataset'}
            
            # 데이터셋 찾기
            target_dataset = self._find_target_dataset(root, ns)
            if not target_dataset:
                return []
            
            # 데이터 추출
            sales_data = self._extract_data_from_dataset(target_dataset, ns)
            
            print(f"📊 총 {len(sales_data)}건의 데이터 추출")
            self._display_sample_data(sales_data)
            
            return sales_data
            
        except ET.ParseError as e:
            print(f"❌ XML 파싱 오류: {str(e)}")
            with open('error_response.xml', 'w', encoding='utf-8') as f:
                f.write(xml_text)
            print("오류 응답을 error_response.xml 파일에 저장했습니다.")
            return []
    
    def _find_target_dataset(self, root, ns):
        """대상 데이터셋 찾기"""
        datasets = root.findall('.//ns:Dataset', ns)
        print(f"🔍 발견된 데이터셋 개수: {len(datasets)}")
        
        for dataset in datasets:
            dataset_id = dataset.get('id')
            print(f"  - 데이터셋 ID: {dataset_id}")
        
        # 데이터가 있는 데이터셋 찾기
        for dataset in datasets:
            rows = dataset.find('.//ns:Rows', ns)
            if rows is not None and len(rows.findall('.//ns:Row', ns)) > 0:
                print(f"✅ 데이터가 있는 데이터셋 사용: {dataset.get('id')}")
                return dataset
        
        return None
    
    def _extract_data_from_dataset(self, dataset, ns):
        """데이터셋에서 데이터 추출"""
        # 컬럼 정보 추출
        columns = []
        column_info = dataset.find('.//ns:ColumnInfo', ns)
        if column_info is not None:
            for col in column_info.findall('.//ns:Column', ns):
                col_id = col.get('id')
                columns.append(col_id)
        
        # 행 데이터 추출
        sales_data = []
        rows = dataset.find('.//ns:Rows', ns)
        if rows is not None:
            row_elements = rows.findall('.//ns:Row', ns)
            print(f"🔢 발견된 행 개수: {len(row_elements)}")
            
            for row in row_elements:
                record = {}
                for col in row.findall('.//ns:Col', ns):
                    col_id = col.get('id')
                    col_value = col.text if col.text else ''
                    record[col_id] = col_value
                
                # 지점명 자동 추가
                if 'strCd' in record:
                    store_code = record['strCd']
                    store_name = self._get_store_name(store_code)
                    record['지점명'] = store_name
                
                sales_data.append(record)
        
        return sales_data
    
    def _get_store_name(self, store_code):
        """지점 코드를 지점명으로 변환"""
        if store_code in self.store_mapping:
            return self.store_mapping[store_code]
        
        str_code = str(store_code)
        if str_code in self.store_mapping:
            return self.store_mapping[str_code]
        
        try:
            num_code = int(float(str(store_code)))
            if num_code in self.store_mapping:
                return self.store_mapping[num_code]
        except:
            pass
        
        return f"지점코드_{store_code}"
    
    def _display_sample_data(self, sales_data):
        """샘플 데이터 출력"""
        display_count = min(3, len(sales_data))
        for i in range(display_count):
            record = sales_data[i]
            key_fields = ['strCd', '지점명', 'slDt', 'tayNm', 'brndNm', 'prodNm', 'prdcd']
            display_record = {k: record.get(k, '') for k in key_fields if k in record}
            print(f"[{i+1}] {display_record}")
        
        if len(sales_data) > 3:
            print(f"... 및 {len(sales_data) - 3}개 추가 레코드")
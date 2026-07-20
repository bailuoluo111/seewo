#!/usr/bin/env python3
"""快速测试单个模块"""

from seewo_data_extractor import SeewoDataExtractor
import json

# 测试提取学生互动数据
extractor = SeewoDataExtractor(report_id="96f58e78b80c462cb1194fa2f6ef4e97")

print("测试提取学生互动数据...")
data = extractor.extract_student_interaction()
print(json.dumps(data, ensure_ascii=False, indent=2))

extractor.close()
print("\n✓ 测试完成")

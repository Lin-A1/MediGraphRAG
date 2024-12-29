from docx import Document
import json

def create_docx(questions, filename):
    # 创建 Word 文档对象
    doc = Document()

    # 添加标题
    doc.add_heading('医学问题与解析', level=1)

    # 遍历每个问题
    for i, question in enumerate(questions, 1):
        # 添加问题编号和题干
        doc.add_heading(f'问题 {i}', level=2)
        doc.add_paragraph(question['topic'])

        # 添加选项
        options = question['options']
        for key, value in options.items():
            doc.add_paragraph(f"{key}. {value}", style='List Bullet')

        # 添加答案
        doc.add_heading('答案', level=3)
        doc.add_paragraph(f"正确答案: {question['answer']}")

        # 添加解析
        doc.add_heading('解析', level=3)
        doc.add_paragraph(question['parse'])

    # 保存文档
    doc.save(filename)


with open('../questionGeneration.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)

# 生成 Word 文档
output_filename = "../医学问题与解析.docx"
create_docx(questions, output_filename)
print(f"文档已保存为 {output_filename}")

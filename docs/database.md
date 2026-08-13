# Document 数据库设计

项目使用 SQLite 保存文档处理记录。

数据库文件：

```text
data/enterprise_ai.db
```

## documents 表

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| id | INTEGER | 文档唯一编号 |
| filename | TEXT | 原始文件名 |
| file_type | TEXT | pdf、docx 或 markdown |
| content_type | TEXT | 文件 MIME 类型 |
| size | INTEGER | 文件大小，单位为字节 |
| status | TEXT | 文档处理状态 |
| created_at | TEXT | 文档创建时间 |

## 状态设计

- `parsed`：文件已经成功解析。
- `failed`：文件解析失败，计划在 Day 13 使用。
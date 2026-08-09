#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
從 MS SQL Server 匯出所有資料表的 DDL（CREATE TABLE）語句。
目標資料庫：openSQLDB @ 192.168.153.12
輸出目錄：C:\git_repos\mmsystem\docs\db
"""

import os
import pymssql

# === 連線設定 ===
SERVER = "192.168.153.12"
DATABASE = "openSQLDB"
USER = "tccifz"
PASSWORD = "fztcs"

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_connection():
    return pymssql.connect(
        server=SERVER,
        user=USER,
        password=PASSWORD,
        database=DATABASE,
        charset="utf8",
    )


def get_all_tables(cursor):
    """取得所有使用者資料表（schema + table_name）"""
    cursor.execute("""
        SELECT s.name AS schema_name, t.name AS table_name
        FROM sys.tables t
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE t.type = 'U'
        ORDER BY s.name, t.name
    """)
    return cursor.fetchall()


def get_columns(cursor, schema, table):
    """取得資料表的所有欄位定義"""
    cursor.execute("""
        SELECT
            c.name AS column_name,
            tp.name AS type_name,
            c.max_length,
            c.precision,
            c.scale,
            c.is_nullable,
            c.is_identity,
            ic.seed_value,
            ic.increment_value,
            dc.definition AS default_value,
            c.collation_name
        FROM sys.columns c
        JOIN sys.types tp ON c.user_type_id = tp.user_type_id
        LEFT JOIN sys.identity_columns ic ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
        WHERE c.object_id = OBJECT_ID(%s)
        ORDER BY c.column_id
    """, (f"{schema}.{table}",))
    return cursor.fetchall()


def get_primary_keys(cursor, schema, table):
    """取得主鍵資訊"""
    cursor.execute("""
        SELECT
            kc.name AS constraint_name,
            COL_NAME(ic.object_id, ic.column_id) AS column_name,
            ic.is_descending_key
        FROM sys.key_constraints kc
        JOIN sys.index_columns ic ON kc.unique_index_id = ic.index_id AND kc.parent_object_id = ic.object_id
        WHERE kc.parent_object_id = OBJECT_ID(%s)
          AND kc.type = 'PK'
        ORDER BY ic.key_ordinal
    """, (f"{schema}.{table}",))
    return cursor.fetchall()


def get_unique_constraints(cursor, schema, table):
    """取得唯一約束"""
    cursor.execute("""
        SELECT
            kc.name AS constraint_name,
            COL_NAME(ic.object_id, ic.column_id) AS column_name,
            ic.is_descending_key
        FROM sys.key_constraints kc
        JOIN sys.index_columns ic ON kc.unique_index_id = ic.index_id AND kc.parent_object_id = ic.object_id
        WHERE kc.parent_object_id = OBJECT_ID(%s)
          AND kc.type = 'UQ'
        ORDER BY kc.name, ic.key_ordinal
    """, (f"{schema}.{table}",))
    return cursor.fetchall()


def get_foreign_keys(cursor, schema, table):
    """取得外來鍵約束"""
    cursor.execute("""
        SELECT
            fk.name AS fk_name,
            COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS parent_column,
            OBJECT_SCHEMA_NAME(fkc.referenced_object_id) AS ref_schema,
            OBJECT_NAME(fkc.referenced_object_id) AS ref_table,
            COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS ref_column,
            fk.delete_referential_action_desc,
            fk.update_referential_action_desc
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        WHERE fk.parent_object_id = OBJECT_ID(%s)
        ORDER BY fk.name, fkc.constraint_column_id
    """, (f"{schema}.{table}",))
    return cursor.fetchall()


def get_check_constraints(cursor, schema, table):
    """取得 CHECK 約束"""
    cursor.execute("""
        SELECT name, definition
        FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID(%s)
        ORDER BY name
    """, (f"{schema}.{table}",))
    return cursor.fetchall()


def get_indexes(cursor, schema, table):
    """取得非主鍵、非唯一約束的索引"""
    cursor.execute("""
        SELECT
            i.name AS index_name,
            i.is_unique,
            i.type_desc,
            COL_NAME(ic.object_id, ic.column_id) AS column_name,
            ic.is_descending_key,
            ic.is_included_column
        FROM sys.indexes i
        JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        WHERE i.object_id = OBJECT_ID(%s)
          AND i.is_primary_key = 0
          AND i.is_unique_constraint = 0
          AND i.type > 0
        ORDER BY i.name, ic.key_ordinal, ic.index_column_id
    """, (f"{schema}.{table}",))
    return cursor.fetchall()


def safe_int(val, default=1):
    """安全轉換 identity seed/increment 值（可能是 int、bytes 或 Decimal）"""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, bytes):
        return int.from_bytes(val, byteorder="little", signed=True)
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def format_column_type(type_name, max_length, precision, scale):
    """格式化欄位型別"""
    # 不帶長度的型別
    no_length_types = {
        "int", "bigint", "smallint", "tinyint", "bit",
        "money", "smallmoney", "float", "real",
        "date", "datetime", "datetime2", "datetimeoffset",
        "smalldatetime", "time", "timestamp",
        "text", "ntext", "image",
        "uniqueidentifier", "xml", "sql_variant",
        "geography", "geometry", "hierarchyid",
    }
    if type_name.lower() in no_length_types:
        return type_name.upper()

    if type_name.lower() in ("decimal", "numeric"):
        return f"{type_name.upper()}({precision}, {scale})"

    if type_name.lower() in ("nvarchar", "nchar"):
        if max_length == -1:
            return f"{type_name.upper()}(MAX)"
        return f"{type_name.upper()}({max_length // 2})"

    if type_name.lower() in ("varchar", "char", "varbinary", "binary"):
        if max_length == -1:
            return f"{type_name.upper()}(MAX)"
        return f"{type_name.upper()}({max_length})"

    return type_name.upper()


def generate_ddl(cursor, schema, table):
    """產生一個資料表完整的 CREATE TABLE DDL"""
    full_name = f"[{schema}].[{table}]"
    columns = get_columns(cursor, schema, table)
    pks = get_primary_keys(cursor, schema, table)
    uqs = get_unique_constraints(cursor, schema, table)
    fks = get_foreign_keys(cursor, schema, table)
    checks = get_check_constraints(cursor, schema, table)

    lines = []
    lines.append(f"CREATE TABLE {full_name} (")

    col_defs = []
    for col in columns:
        (col_name, type_name, max_length, precision, scale,
         is_nullable, is_identity, seed_val, incr_val, default_val, collation) = col

        col_type = format_column_type(type_name, max_length, precision, scale)
        parts = [f"    [{col_name}]", col_type]

        if is_identity:
            seed = safe_int(seed_val, 1)
            incr = safe_int(incr_val, 1)
            parts.append(f"IDENTITY({seed},{incr})")

        if not is_nullable:
            parts.append("NOT NULL")
        else:
            parts.append("NULL")

        if default_val:
            parts.append(f"DEFAULT {default_val}")

        col_defs.append(" ".join(parts))

    # 主鍵
    if pks:
        pk_name = pks[0][0]
        pk_cols = ", ".join(
            f"[{r[1]}]{' DESC' if r[2] else ''}" for r in pks
        )
        col_defs.append(f"    CONSTRAINT [{pk_name}] PRIMARY KEY ({pk_cols})")

    # 唯一約束
    if uqs:
        uq_groups = {}
        for r in uqs:
            uq_groups.setdefault(r[0], []).append(r)
        for uq_name, cols in uq_groups.items():
            uq_cols = ", ".join(
                f"[{r[1]}]{' DESC' if r[2] else ''}" for r in cols
            )
            col_defs.append(f"    CONSTRAINT [{uq_name}] UNIQUE ({uq_cols})")

    # CHECK 約束
    for chk in checks:
        col_defs.append(f"    CONSTRAINT [{chk[0]}] CHECK {chk[1]}")

    lines.append(",\n".join(col_defs))
    lines.append(");\nGO\n")

    ddl = "\n".join(lines)

    # 外來鍵（ALTER TABLE）
    if fks:
        fk_groups = {}
        for r in fks:
            fk_groups.setdefault(r[0], []).append(r)
        for fk_name, cols in fk_groups.items():
            parent_cols = ", ".join(f"[{r[1]}]" for r in cols)
            ref_schema = cols[0][2]
            ref_table = cols[0][3]
            ref_cols = ", ".join(f"[{r[4]}]" for r in cols)
            del_action = cols[0][5]
            upd_action = cols[0][6]

            fk_sql = (
                f"ALTER TABLE {full_name}\n"
                f"    ADD CONSTRAINT [{fk_name}]\n"
                f"    FOREIGN KEY ({parent_cols})\n"
                f"    REFERENCES [{ref_schema}].[{ref_table}] ({ref_cols})"
            )
            actions = []
            if del_action and del_action != "NO_ACTION":
                actions.append(f"ON DELETE {del_action.replace('_', ' ')}")
            if upd_action and upd_action != "NO_ACTION":
                actions.append(f"ON UPDATE {upd_action.replace('_', ' ')}")
            if actions:
                fk_sql += "\n    " + " ".join(actions)
            fk_sql += ";\nGO\n"
            ddl += "\n" + fk_sql

    # 索引
    indexes = get_indexes(cursor, schema, table)
    if indexes:
        idx_groups = {}
        for r in indexes:
            idx_groups.setdefault(r[0], {"is_unique": r[1], "type_desc": r[2], "key_cols": [], "include_cols": []})
            if r[5]:  # is_included_column
                idx_groups[r[0]]["include_cols"].append(r[3])
            else:
                idx_groups[r[0]]["key_cols"].append((r[3], r[4]))

        for idx_name, info in idx_groups.items():
            unique = "UNIQUE " if info["is_unique"] else ""
            idx_type = "NONCLUSTERED" if "NONCLUSTERED" in info["type_desc"] else info["type_desc"]
            key_cols = ", ".join(
                f"[{c}]{' DESC' if desc else ''}" for c, desc in info["key_cols"]
            )
            idx_sql = f"CREATE {unique}{idx_type} INDEX [{idx_name}]\n    ON {full_name} ({key_cols})"
            if info["include_cols"]:
                inc = ", ".join(f"[{c}]" for c in info["include_cols"])
                idx_sql += f"\n    INCLUDE ({inc})"
            idx_sql += ";\nGO\n"
            ddl += "\n" + idx_sql

    return ddl


def main():
    print(f"連線至 {SERVER}/{DATABASE} ...")
    conn = get_connection()
    cursor = conn.cursor()

    tables = get_all_tables(cursor)
    print(f"找到 {len(tables)} 個資料表")

    all_ddl = []
    all_ddl.append(f"-- ============================================")
    all_ddl.append(f"-- Database: {DATABASE}")
    all_ddl.append(f"-- Server:   {SERVER}")
    all_ddl.append(f"-- Generated DDL for all user tables")
    all_ddl.append(f"-- ============================================\n")

    for schema, table in tables:
        print(f"  處理: [{schema}].[{table}]")
        try:
            ddl = generate_ddl(cursor, schema, table)
            all_ddl.append(f"-- ----------------------------------------")
            all_ddl.append(f"-- Table: [{schema}].[{table}]")
            all_ddl.append(f"-- ----------------------------------------")
            all_ddl.append(ddl)
        except Exception as e:
            msg = f"-- ERROR generating DDL for [{schema}].[{table}]: {e}"
            print(f"  *** {msg}")
            all_ddl.append(msg)

    # 寫入合併檔案
    output_file = os.path.join(OUTPUT_DIR, "openSQLDB_DDL.sql")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(all_ddl))

    print(f"\nDDL 已匯出至: {output_file}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()

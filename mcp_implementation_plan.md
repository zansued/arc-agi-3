# MCP Implementation Plan for Supabase and CPF Data

## Overview
Implement Model Context Protocol (MCP) servers for Agent Zero to access Supabase database and manage CPF data (152.9M records) efficiently.

## Phase 1: Enable MCP in Agent Zero

### 1.1 Update Settings
- Enable MCP server in `/a0/usr/settings.json`
- Configure MCP servers for Supabase access

### 1.2 Test MCP Connectivity
- Start MCP server
- Verify tools are exposed

## Phase 2: Supabase MCP Server

### 2.1 Create Supabase MCP Server
- File: `/a0/usr/workdir/mcp_servers/supabase_mcp.py`
- Tools:
  - `supabase_query`: Execute SQL queries
  - `supabase_insert`: Insert data
  - `supabase_update`: Update data
  - `supabase_delete`: Delete data
  - `supabase_list_tables`: List tables

### 2.2 Database Connection
- Use PostgreSQL connection pool
- Connection string: `postgresql://postgres:postgres@supabase-db:5432/postgres`
- Handle connection errors gracefully

## Phase 3: CPF Database Migration

### 3.1 Database Schema Design
```sql
-- Partitioned table by region
CREATE TABLE cpfs (
    id BIGSERIAL,
    cpf VARCHAR(11) NOT NULL,
    nome VARCHAR(200) NOT NULL,
    genero VARCHAR(20),
    data_nascimento DATE,
    estado VARCHAR(2),
    arquivo_origem VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (id, estado)
) PARTITION BY LIST (estado);

-- Create partitions for each state
CREATE TABLE cpfs_rs PARTITION OF cpfs FOR VALUES IN ('RS');
CREATE TABLE cpfs_df PARTITION OF cpfs FOR VALUES IN ('DF');
-- ... etc for all states

-- Indexes for fast queries
CREATE INDEX idx_cpf_cpf ON cpfs(cpf);
CREATE INDEX idx_cpf_nome ON cpfs(nome);
CREATE INDEX idx_cpf_data_nascimento ON cpfs(data_nascimento);
```

### 3.2 Data Migration Strategy
- Use PostgreSQL COPY command for bulk loading
- Process files in parallel
- Validate data format
- Handle duplicates
- Monitor progress

### 3.3 Migration Script
- Python script to read 8 TXT files
- Parse `CPF|NOME|GÊNERO|DATA_NASCIMENTO` format
- Bulk insert using COPY
- Progress reporting
- Error handling

## Phase 4: CPF MCP Server

### 4.1 Create CPF MCP Server
- File: `/a0/usr/workdir/mcp_servers/cpf_mcp.py`
- Tools:
  - `cpf_search_by_number`: Search by CPF
  - `cpf_search_by_name`: Search by name (fuzzy)
  - `cpf_search_by_birthdate`: Search by birthdate
  - `cpf_get_stats`: Get statistics
  - `cpf_export_results`: Export search results

### 4.2 Optimized Queries
- Use prepared statements
- Implement pagination
- Add query caching
- Support fuzzy search for names

## Phase 5: Skills MCP Server

### 5.1 Create Skills MCP Server
- File: `/a0/usr/workdir/mcp_servers/skills_mcp.py`
- Tools:
  - `skills_list`: List all skills
  - `skills_search`: Search skills
  - `skills_get`: Get skill details
  - `skills_update`: Update skill
  - `skills_import`: Import from filesystem

### 5.2 Skills Database Schema
```sql
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    file_path VARCHAR(500),
    language VARCHAR(20),
    tags TEXT[],
    usage_count INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Phase 6: Integration and Testing

### 6.1 Integration with Agent Zero
- Register MCP servers in settings
- Test tool discovery
- Verify response format

### 6.2 Performance Testing
- Test CPF queries with 152M records
- Measure response times
- Optimize indexes
- Test concurrent access

### 6.3 Security
- Validate SQL queries
- Prevent SQL injection
- Implement rate limiting
- Audit logging

## Timeline

### Week 1
- Enable MCP and create Supabase MCP Server
- Design CPF database schema

### Week 2
- Implement CPF data migration
- Create CPF MCP Server

### Week 3
- Create Skills MCP Server
- Integration testing

### Week 4
- Performance optimization
- Documentation

## Success Metrics

### Performance
- CPF search: < 100ms for exact match
- Bulk insert: > 100k records/minute
- Concurrent queries: Support 10+ simultaneous

### Reliability
- 99.9% uptime
- Data consistency
- Backup and recovery

### Usability
- Intuitive tool names
- Clear documentation
- Error messages

## Next Steps
1. Enable MCP in settings
2. Create Supabase MCP Server
3. Test basic database connectivity
4. Start CPF schema design
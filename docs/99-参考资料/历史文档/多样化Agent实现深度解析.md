# 多样化 Agent 实现深度解析

本文档详细介绍 GraphRAG 系统中的 5 种 Agent 实现，包括设计理念、技术细节、工作流程、适用场景和性能对比。

---

## 📊 Agent 全景对比

| Agent 类型 | 复杂度 | 搜索策略 | ���理能力 | 适用场景 | 响应速度 |
|-----------|--------|---------|---------|---------|---------|
| **NaiveRagAgent** | ⭐ | 向量检索 | 简单 | 基础问答 | ⚡⚡⚡ 最快 |
| **HybridAgent** | ⭐⭐ | 混合检索 | 中等 | 通用问答 | ⚡⚡ 快 |
| **GraphAgent** | ⭐⭐⭐ | 图+向量 | 中高 | 结构化知识 | ⚡ 中等 |
| **DeepResearchAgent** | ⭐⭐⭐⭐ | 多轮推理 | 高 | 复杂问题 | 🐌 慢 |
| **FusionGraphRAGAgent** | ⭐⭐⭐⭐⭐ | 多Agent协作 | 极高 | 研究报告 | 🐌🐌 最慢 |

---

## 1️⃣ NaiveRagAgent - 基础向量检索

### 核心设计理念

**"简单快速，满足基本需求"**

NaiveRagAgent 是最简单的实现，仅使用向量检索，适合快速原型开发和基础问答场景。

### 技术架构

```
用户问题
    ↓
向量编码 (Embeddings)
    ↓
Neo4j 向量索引检索
    ↓
Top-K 相似 Chunks
    ↓
LLM 生成答案
    ↓
返回结果
```

### 关键代码实现

**文件**: `backend/graphrag_agent/agents/naive_rag_agent.py`

```python
class NaiveRagAgent(BaseAgent):
    """使用简单向量检索的Naive RAG Agent实现"""

    def __init__(self):
        # 🔑 只初始化一个工具：NaiveSearchTool
        self.search_tool = NaiveSearchTool()
        self.cache_dir = "./cache/naive_agent"
        super().__init__(cache_dir=self.cache_dir)

    def _setup_tools(self) -> List:
        """设置工具 - 只有一个向量检索工具"""
        return [
            self.search_tool.get_tool(),  # ← 只有这一个工具
        ]

    def _extract_keywords(self, query: str) -> Dict[str, List[str]]:
        """不做关键词提取，返回空列表"""
        return {"low_level": [], "high_level": []}

    def _generate_node(self, state):
        """生成回答 - 直接使用检索结果"""
        messages = state["messages"]

        # 获取问题和检索结果
        question = messages[-3].content
        docs = messages[-1].content  # NaiveSearchTool 返回的文本

        # 检查缓存
        cached_result = self.cache_manager.get(question, thread_id=thread_id)
        if cached_result:
            return {"messages": [AIMessage(content=cached_result)]}

        # 🔑 简单的 Prompt + LLM 生成
        prompt = ChatPromptTemplate.from_messages([
            ("system", NAIVE_PROMPT),
            ("human", NAIVE_RAG_HUMAN_PROMPT),
        ])

        rag_chain = prompt | self.llm | StrOutputParser()
        response = rag_chain.invoke({
            "context": docs,
            "question": question,
            "response_type": response_type
        })

        return {"messages": [AIMessage(content=response)]}
```

### NaiveSearchTool 实现

**文件**: `backend/graphrag_agent/search/tool/naive_search_tool.py`

```python
class NaiveSearchTool:
    """最简单的向量检索工具"""

    def search(self, query: str) -> str:
        """
        执行向量检索

        工作流程:
        1. 将查询编码为向量
        2. 在 Neo4j chunk_index 中执行相似度搜索
        3. 返回 Top-K 个最相似的文本块
        """
        # 1. 向量化查询
        query_embedding = self.embeddings.embed_query(query)

        # 2. Neo4j 向量检索
        vector_store = Neo4jVector.from_existing_index(
            self.embeddings,
            index_name="chunk_index",  # ← 只用 chunk 索引
            retrieval_query="""
                MATCH (chunk:__Chunk__)
                WHERE chunk.id = $chunk_id
                RETURN chunk.text AS text
            """
        )

        # 3. 相似度搜索
        docs = vector_store.similarity_search(query, k=5)

        # 4. 拼接文本
        return "\n\n".join([doc.page_content for doc in docs])
```

### 工作流程图

```
【START】
    ↓
【agent 节点】
    - 接收用户问题
    - 决定调用 naive_search_tool
    ↓
【retrieve 节点】
    - 向量编码: "旷课多少学时会被退学？"
    - Neo4j 向量检索: chunk_index.similarity_search(vector, k=5)
    - 返回: ["chunk1文本", "chunk2文本", ...]
    ↓
【generate 节点】
    - Prompt: 基于以下信息回答问题: {context}
    - LLM 生成: "根据规定，旷课累计达到40学时..."
    ↓
【END】
```

### 优缺点分析

#### ✅ 优点

1. **极快响应速度**
   - 单次向量检索，平均耗时 < 500ms
   - 适合实时对话场景

2. **简单易理解**
   - 代码量少，易于维护
   - 适合学习和原型开发

3. **低资源消耗**
   - 只需一次 LLM 调用
   - 内存占用小

#### ❌ 缺点

1. **检索质量有限**
   - 无法利用图结构信息
   - 只能检索到相似文本块

2. **缺乏推理能力**
   - 无多跳推理
   - 无法处理复杂问题

3. **上下文有限**
   - Top-K 限制可能遗漏重要信息
   - 无法整合多个知识源

### 适用场景

✅ **适合**:
- 简单事实问答（"谁是某人？"）
- FAQ 系统
- 快速原型开发
- 资源受限环境

❌ **不适合**:
- 需要推理的问题（"为什么...？"）
- 多步骤问题
- 需要图结构信息的查询

---

## 2️⃣ HybridAgent - 混合检索策略

### 核心设计理念

**"结合实体细节和主题概念，平衡精度与覆盖面"**

HybridAgent 使用混合搜索策略，同时利用：
- **低级关键词** (Low-level): 实体名称、具体细节
- **高级关键词** (High-level): 主题、概念、类别

### 技术架构

```
用户问题
    ↓
关键词提取 (LLM)
    ├─ 低级关键词: ["旷课", "40学时", "退学"]
    └─ 高级关键词: ["学生管理", "处分制度", "学籍管理"]
    ↓
并行检索
    ├─ Local Search (实体中心)
    └─ Global Search (社区聚合)
    ↓
结果融合
    ↓
LLM 生成答案
```

### 关键代码实现

**文件**: `backend/graphrag_agent/agents/hybrid_agent.py`

```python
class HybridAgent(BaseAgent):
    """使用混合搜索的Agent实现"""

    def __init__(self):
        # 🔑 初始化混合搜索工具
        self.search_tool = HybridSearchTool()
        self.cache_dir = "./cache/hybrid_agent"
        super().__init__(cache_dir=self.cache_dir)

    def _setup_tools(self) -> List:
        """设置工具 - 本地和全局搜索"""
        return [
            self.search_tool.get_tool(),         # ← Local Search
            self.search_tool.get_global_tool(),  # ← Global Search
        ]

    def _extract_keywords(self, query: str) -> Dict[str, List[str]]:
        """提取查询关键词 - 双层关键词"""
        keywords = self.search_tool.extract_keywords(query)

        # 返回格式:
        # {
        #     "low_level": ["旷课", "40学时", "退学"],
        #     "high_level": ["学生管理", "处分制度"]
        # }
        return keywords

    def _generate_node(self, state):
        """生成回答 - 基于混合检索结果"""
        messages = state["messages"]
        question = messages[-3].content
        docs = messages[-1].content

        # 缓存检查
        cached_result = self.cache_manager.get(question, thread_id=thread_id)
        if cached_result:
            return {"messages": [AIMessage(content=cached_result)]}

        # 🔑 使用混合检索结果生成答案
        prompt = ChatPromptTemplate.from_messages([
            ("system", LC_SYSTEM_PROMPT),
            ("human", HYBRID_AGENT_GENERATE_PROMPT),
        ])

        rag_chain = prompt | self.llm | StrOutputParser()
        response = rag_chain.invoke({
            "context": docs,  # ← 混合检索的结果
            "question": question,
            "response_type": response_type
        })

        return {"messages": [AIMessage(content=response)]}
```

### HybridSearchTool 实现

**文件**: `backend/graphrag_agent/search/tool/hybrid_tool.py`

```python
class HybridSearchTool:
    """混合搜索工具"""

    def __init__(self):
        # 初始化本地和全局搜索器
        self.local_searcher = LocalSearch(llm, embeddings)
        self.global_searcher = GlobalSearch(llm, embeddings)

    def search(self, query: str, keywords: Dict) -> str:
        """
        执行混合搜索

        步骤:
        1. 提取低级和高级关键词
        2. 本地搜索: 基于实体的邻域扩展
        3. 全局搜索: 基于社区的主题聚合
        4. 融合结果
        """
        low_level = keywords.get("low_level", [])
        high_level = keywords.get("high_level", [])

        # 1. 本地搜索 (实体中心)
        local_result = self.local_searcher.search(
            query=query,
            entities=low_level  # ← 使用低级关键词
        )

        # 2. 全局搜索 (社区聚合)
        global_result = self.global_searcher.search(
            query=query,
            concepts=high_level  # ← 使用高级关键词
        )

        # 3. 融合结果
        combined = f"""
        【实体详细信息】
        {local_result}

        【主题概念总结】
        {global_result}
        """

        return combined

    def extract_keywords(self, query: str) -> Dict:
        """
        提取双层关键词

        使用 LLM 提取:
        - low_level: 实体名称、具体细节
        - high_level: 主题、概念、类别
        """
        prompt = f"""
        分析以下查询，提取关键词:

        查询: {query}

        请提取:
        1. 低级关键词 (实体、数字、具体名词)
        2. 高级关键词 (主题、概念、类别)

        返回 JSON 格式:
        {{
            "low_level": ["关键词1", "关键词2"],
            "high_level": ["主题1", "主题2"]
        }}
        """

        result = self.llm.invoke(prompt)
        return json.loads(result.content)
```

### 检索示例

**查询**: "旷课多少学时会被退学？"

**关键词提取**:
```json
{
    "low_level": ["旷课", "40学时", "退学", "处分"],
    "high_level": ["学生管理制度", "学籍管理", "违纪处理"]
}
```

**Local Search** (实体中心):
```
【检索流程】
1. 向量检索: "旷课" → Entity: "旷课处分"
2. 邻域扩展:
   - (旷课处分)-[:累计达到]->(40学时)
   - (旷课处分)-[:导致]->(退学处分)
3. 返回: 实体详细描述 + 关系链
```

**Global Search** (社区聚合):
```
【检索流程】
1. 匹配社区: "学生管理制度" → Community #5
2. 社区摘要:
   - 包含: 旷课管理、处分流程、学籍管理
   - 摘要: 详细阐述学生管理规定...
3. 返回: 社区级别的主题总结
```

**融合结果**:
```
【实体详细信息】
旷课处分规定:
- 累计旷课达到 40 学时，给予退学处分
- 处理流程: 通知家长 → 学生辩护 → 学校审批
- 相关规定: 《学生违纪处分条例》第12条

【主题概念总结】
学生管理制度涵盖:
1. 考勤管理: 旷课统计、请假流程
2. 处分类型: 警告、严重警告、退学
3. 救济途径: 申诉流程、复议机制
```

### 优缺点分析

#### ✅ 优点

1. **检索质量高**
   - 双层关键词提高召回率
   - 结合实体细节和主题概念

2. **覆盖面广**
   - Local Search 提供精确信息
   - Global Search 提供背景知识

3. **平衡性好**
   - 响应速度适中 (1-3 秒)
   - 答案质量较高

#### ❌ 缺点

1. **关键词提取依赖 LLM**
   - 额外一次 LLM 调用
   - 可能提取不准确

2. **结果融合简单**
   - 只是拼接，未深度整合
   - 可能存在冗余信息

### 适用场景

✅ **适合**:
- 通用问答系统 **(推荐默认选择)**
- 需要平衡速度和质量
- 中等复杂度问题

❌ **不适合**:
- 极简单问题（可用 NaiveRag）
- 极复杂问题（需用 DeepResearch）

---

## 3️⃣ GraphAgent - 图结构推理

### 核心设计理念

**"利用图结构，支持评分和聚合操作"**

GraphAgent 充分利用知识图谱的结构信息，支持：
- **文档评分**: 判断检索结果质量
- **Reduce 操作**: 对全局搜索结果进行聚合
- **多跳推理**: 沿着图结构进行推理

### 技术架构

```
用户问题
    ↓
关键词提取 (LLM)
    ↓
Local/Global Search 决策
    ├─ Local Search → 文档评分
    │       ├─ 质量好 → Generate
    │       └─ 质量差 → 重新检索
    │
    └─ Global Search → Reduce 节点
            ↓
        Map-Reduce 聚合
            ↓
        生成答案
```

### 关键代码实现

**文件**: `backend/graphrag_agent/agents/graph_agent.py`

```python
class GraphAgent(BaseAgent):
    """使用图结构的Agent实现"""

    def __init__(self):
        # 🔑 本地和全局搜索工具
        self.local_tool = LocalSearchTool()
        self.global_tool = GlobalSearchTool()
        self.cache_dir = "./cache/graph_agent"
        super().__init__(cache_dir=self.cache_dir)

    def _setup_tools(self) -> List:
        """设置工具"""
        return [
            self.local_tool.get_tool(),   # ← Local Search
            self.global_tool.search,       # ← Global Search
        ]

    def _add_retrieval_edges(self, workflow):
        """🔑 添加条件路由 - 核心特色"""

        # 1. 添加 reduce 节点
        workflow.add_node("reduce", self._reduce_node)

        # 2. 🔑 添加条件边 - 文档评分决定路由
        workflow.add_conditional_edges(
            "retrieve",
            self._grade_documents,  # ← 评分函数
            {
                "generate": "generate",  # ← 质量好，直接生成
                "reduce": "reduce"       # ← 全局搜索，需要聚合
            }
        )

        # 3. Reduce 后直接结束
        workflow.add_edge("reduce", END)

    def _grade_documents(self, state) -> str:
        """
        🔑 文档评分 - 决定路由方向

        返回:
        - "generate": 使用 Local Search，文档质量好
        - "reduce": 使用 Global Search，需要 Map-Reduce
        """
        messages = state["messages"]
        retrieve_message = messages[-2]

        # 1. 检查是否为全局检索
        tool_calls = retrieve_message.additional_kwargs.get("tool_calls", [])
        if tool_calls and tool_calls[0].get("function", {}).get("name") == "global_retriever":
            return "reduce"  # ← 全局搜索 → Reduce

        # 2. 评估文档质量
        question = messages[-3].content
        docs = messages[-1].content

        # 检查文档长度
        if not docs or len(docs) < 100:
            # 文档不足，尝试重新检索
            try:
                local_result = self.local_tool.search(question)
                if local_result and len(local_result) > 100:
                    messages[-1].content = local_result
            except Exception as e:
                print(f"本地搜索失败: {e}")

        # 3. 检查关键词覆盖
        keywords = self._extract_keywords_from_message(messages[-3])
        keyword_coverage = self._calculate_keyword_coverage(docs, keywords)

        if keyword_coverage > 0.5:  # 覆盖率 > 50%
            return "generate"  # ← 质量好
        else:
            return "generate"  # ← 默认生成（避免死循环）

    def _reduce_node(self, state):
        """
        🔑 Reduce 节点 - Map-Reduce 聚合

        用于处理全局搜索的结果，通过 Map-Reduce 整合多个社区的信息
        """
        messages = state["messages"]
        question = messages[-3].content
        search_results = messages[-1].content

        # 1. 解析全局搜索结果 (多个社区的摘要)
        community_summaries = self._parse_community_results(search_results)

        # 2. Map 阶段: 每个社区生成局部答案
        partial_answers = []
        for community in community_summaries:
            prompt = f"""
            基于以下社区摘要回答问题:

            社区摘要: {community["summary"]}
            问题: {question}

            提取与问题相关的信息。
            """
            partial_answer = self.llm.invoke(prompt).content
            partial_answers.append(partial_answer)

        # 3. Reduce 阶段: 整合所有局部答案
        reduce_prompt = GRAPH_AGENT_REDUCE_PROMPT.format(
            question=question,
            partial_answers="\n\n".join(partial_answers),
            response_type=response_type
        )

        final_answer = self.llm.invoke(reduce_prompt).content

        return {"messages": [AIMessage(content=final_answer)]}

    def _generate_node(self, state):
        """标准生成节点 - 处理 Local Search 结果"""
        messages = state["messages"]
        question = messages[-3].content
        docs = messages[-1].content

        # 缓存检查...

        # 生成答案
        prompt = ChatPromptTemplate.from_messages([
            ("system", LC_SYSTEM_PROMPT),
            ("human", GRAPH_AGENT_GENERATE_PROMPT),
        ])

        rag_chain = prompt | self.llm | StrOutputParser()
        response = rag_chain.invoke({
            "context": docs,
            "question": question,
            "response_type": response_type
        })

        return {"messages": [AIMessage(content=response)]}
```

### 工作流程图

```
【START】
    ↓
【agent 节点】
    - 提取关键词
    - 决定调用 local_tool 或 global_tool
    ↓
【retrieve 节点】
    ├─ Local Search 调用
    │   - 实体中心检索
    │   - 返回: 实体+关系+邻居
    │
    └─ Global Search 调用
        - 社区级聚合
        - 返回: 多个社区摘要
    ↓
【_grade_documents】条件判断
    ├─ 检测到 Global Search → "reduce"
    │       ↓
    │   【reduce 节点】
    │       ├─ Map: 每个社区生成局部答案
    │       └─ Reduce: 整合为最终答案
    │       ↓
    │   【END】
    │
    └─ Local Search / 质量好 → "generate"
            ↓
        【generate 节点】
            - 基于实体信息生成答案
            ↓
        【END】
```

### Map-Reduce 示例

**查询**: "学校有哪些奖学金类型？"

**Global Search 返回**:
```
Community #1 摘要:
- 包含: 国家奖学金、励志奖学金、助学金
- 评选条件: 成绩优异、家庭困难

Community #2 摘要:
- 包含: 校级奖学金、企业奖学金
- 发放流程: 申请、评审、公示

Community #3 摘要:
- 包含: 单项奖学金、创新奖学金
- 奖励范围: 学术、文体、创新
```

**Map 阶段** (每个社区):
```python
# Community #1 局部答案
"学校提供国家奖学金、励志奖学金和助学金，主要面向成绩优异或家庭困难的学生。"

# Community #2 局部答案
"学校提供校级奖学金和企业奖学金，需经过申请、评审和公示流程。"

# Community #3 局部答案
"学校提供单项奖学金和创新奖学金，奖励学术、文体和创新方面的突出表现。"
```

**Reduce 阶段** (整合):
```python
final_answer = """
学校奖学金体系包括以下类型:

1. 国家级奖学金:
   - 国家奖学金、励志奖学金、助学金
   - 面向成绩优异或家庭困难的学生

2. 校级奖学金:
   - 校级综合奖学金、企业奖学金
   - 需经过申请、评审和公示流程

3. 专项奖学金:
   - 单项奖学金、创新奖学金
   - 奖励学术、文体和创新方面的突出表现

申请流程: 提交申请 → 资格审查 → 评审打分 → 公示 → 发放
"""
```

### 优缺点分析

#### ✅ 优点

1. **结构化推理**
   - 利用图结构信息
   - 多跳推理能力

2. **智能路由**
   - 文档评分机制
   - 根据质量动态调整

3. **Map-Reduce 聚合**
   - 整合多个社区信息
   - 适合全局性问题

#### ❌ 缺点

1. **复杂度高**
   - 条件路由增加复杂性
   - Reduce 需要多次 LLM 调用

2. **评分不够精确**
   - 简单的长度和覆盖率判断
   - 可能误判

### 适用场景

✅ **适合**:
- 需要图结构信息的查询
- 全局性、总结性问题
- 需要多跳推理

❌ **不适合**:
- 简单事实查询
- 对响应速度要求极高的场景

---

## 4️⃣ DeepResearchAgent - 多步骤推理链

### 核心设计理念

**"像研究员一样思考：多轮思考-搜索-推理循环"**

DeepResearchAgent 实现了 Chain of Exploration (CoE) 范式，通过多轮迭代深入探索知识图谱。

### 技术架构

```
用户问题
    ↓
【第 1 轮迭代】
    ├─ 思考: 我需要找什么信息？
    ├─ 搜索: KB检索
    ├─ 推理: 信息是否充分？
    └─ 决策: 继续 or 结束
    ↓
【第 2 轮迭代】
    ├─ 思考: 还缺少什么？
    ├─ 搜索: 针对性检索
    ├─ 推理: 整合新信息
    └─ 决策: 继续 or 结束
    ↓
【第 N 轮迭代】
    └─ 最终答案
```

### 关键代码实现

**文件**: `backend/graphrag_agent/agents/deep_research_agent.py`

```python
class DeepResearchAgent(BaseAgent):
    """
    深度研究Agent

    特点:
    1. 显式推理过程 (Chain of Thought)
    2. 迭代式搜索 (Chain of Exploration)
    3. 高质量知识整合
    4. 支持流式输出思考过程
    5. 社区感知和知识图谱增强
    6. 多分支推理和矛盾检测
    """

    def __init__(self, use_deeper_tool=True):
        # 🔑 选择研究工具版本
        self.use_deeper_tool = use_deeper_tool

        if use_deeper_tool:
            # 增强版: DeeperResearchTool
            self.research_tool = DeeperResearchTool()
            self.exploration_tool = self.research_tool.get_exploration_tool()
            self.reasoning_analysis_tool = self.research_tool.get_reasoning_analysis_tool()
        else:
            # 标准版: DeepResearchTool
            self.research_tool = DeepResearchTool()

        self.stream_tool = self.research_tool.get_thinking_stream_tool()
        self.show_thinking = False  # 是否显示思考过程

        super().__init__(cache_dir="./cache/enhanced_research_agent")

    def _setup_tools(self) -> List:
        """设置工具 - 根据模式动态选择"""
        tools = []

        # 基础研究工具
        if self.show_thinking:
            tools.append(self.research_tool.get_thinking_tool())
        else:
            tools.append(self.research_tool.get_tool())

        # 增强工具
        if self.use_deeper_tool:
            tools.append(self.exploration_tool)        # 知识图谱探索
            tools.append(self.reasoning_analysis_tool) # 推理链分析

        # 流式工具
        tools.append(self.stream_tool)

        return tools

    def ask_with_thinking(self, query: str, thread_id: str = "default"):
        """
        🔑 带思考过程的问答

        返回:
        {
            "answer": "最终答案",
            "thinking_process": "【深度研究】第1轮...",
            "execution_logs": [...]
        }
        """
        # 1. 启用思考过程模式
        original_thinking = self.show_thinking
        self.show_thinking = True
        self._setup_tools()  # 重新设置工具

        try:
            # 2. 执行标准流程
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "recursion_limit": 10  # 允许更多迭代
                }
            }

            inputs = {"messages": [HumanMessage(content=query)]}

            # 3. 逐步执行工作流
            for output in self.graph.stream(inputs, config=config):
                pass

            # 4. 获取完整对话历史
            chat_history = self.memory.get(config)["channel_values"]["messages"]

            # 5. 提取思考过程和最终答案
            thinking_process = ""
            final_answer = ""

            for msg in chat_history:
                if isinstance(msg, ToolMessage):
                    # 工具返回的内容可能包含思考过程
                    content = msg.content
                    if "[深度研究]" in content or "[KB检索]" in content:
                        thinking_process += content + "\n\n"

                if isinstance(msg, AIMessage) and msg.content:
                    final_answer = msg.content

            return {
                "answer": final_answer,
                "thinking_process": thinking_process,
                "execution_logs": self.execution_log
            }

        finally:
            # 6. 恢复原始设置
            self.show_thinking = original_thinking
            self._setup_tools()
```

### DeepResearchTool 实现

**文件**: `backend/graphrag_agent/search/tool/deep_research_tool.py`

```python
class DeepResearchTool:
    """深度研究工具 - 实现 Chain of Exploration"""

    def research(self, query: str, show_thinking: bool = False) -> str:
        """
        执行深度研究

        工作流程:
        1. 初始化探索状态
        2. 多轮迭代:
           a. 生成搜索计划
           b. 执行知识库检索
           c. 评估信息充分性
           d. 决定是否继续
        3. 整合所有信息
        4. 生成最终答案
        """
        max_iterations = 5
        iteration = 0
        collected_info = []

        while iteration < max_iterations:
            iteration += 1

            # 🔑 第 1 步: 思考 - 我需要找什么？
            thinking_prompt = f"""
            【深度研究 - 第 {iteration} 轮】

            问题: {query}

            已收集信息:
            {chr(10).join(collected_info) if collected_info else "（无）"}

            请思考:
            1. 现在还缺少什么信息？
            2. 下一步应该搜索什么？
            3. 搜索关键词是什么？

            返回 JSON:
            {{
                "missing_info": "缺少的信息",
                "search_keywords": ["关键词1", "关键词2"],
                "should_continue": true/false
            }}
            """

            thinking_result = self.llm.invoke(thinking_prompt)
            thinking_data = json.loads(thinking_result.content)

            # 如果判断信息充分，结束迭代
            if not thinking_data.get("should_continue", False):
                break

            # 🔑 第 2 步: 搜索 - 执行 KB 检索
            if show_thinking:
                output = f"\n[深度研究] 第 {iteration} 轮\n"
                output += f"思考: {thinking_data['missing_info']}\n"

            search_keywords = thinking_data.get("search_keywords", [])
            search_results = []

            for keyword in search_keywords:
                if show_thinking:
                    output += f"\n[KB检索] 关键词: {keyword}\n"

                # 执行向量检索
                result = self.local_search.search(keyword)
                search_results.append(result)

                if show_thinking:
                    output += f"找到 {len(result)} 条相关信息\n"

            # 🔑 第 3 步: 推理 - 整合新信息
            integration_prompt = f"""
            整合以下检索结果:

            {chr(10).join(search_results)}

            提取与问题相关的关键信息。
            """

            integrated_info = self.llm.invoke(integration_prompt).content
            collected_info.append(integrated_info)

            if show_thinking:
                output += f"\n[推理] 整合信息: {integrated_info[:100]}...\n"
                yield output  # 流式输出思考过程

        # 🔑 第 4 步: 生成最终答案
        final_prompt = f"""
        基于以下深度研究结果回答问题:

        问题: {query}

        研究结果:
        {chr(10).join(collected_info)}

        请给出详细、准确的答案。
        """

        final_answer = self.llm.invoke(final_prompt).content

        if show_thinking:
            yield f"\n【最终答案】\n{final_answer}"
        else:
            return final_answer
```

### 迭代过程示例

**查询**: "学校对学生旷课的处理流程是什么？"

**第 1 轮迭代**:
```
【深度研究】第 1 轮

[思考]
- 缺少信息: 旷课的定义和统计方式
- 搜索关键词: ["旷课", "考勤���理"]
- 继续探索: true

[KB检索] 关键词: 旷课
找到 5 条相关信息:
- 旷课定义: 未经批准缺席课程
- 统计方式: 按学时累计

[推理]
旷课是指学生未经批准缺席教学活动，按学时累计统计。
```

**第 2 轮迭代**:
```
【深度研究】第 2 轮

[思考]
- 缺少信息: 不同程度旷课的处理方式
- 搜索关键词: ["旷课处分", "处理流程"]
- 继续探索: true

[KB检索] 关键词: 旷课处分
找到 8 条相关信息:
- 10学时: 警告
- 20学时: 严重警告
- 40学时: 退学处分

[推理]
根据旷课学时不同，处分程度递增：
10学时警告 → 20学时严重警告 → 40学时退学。
```

**第 3 轮迭代**:
```
【深度研究】第 3 轮

[思考]
- 缺少信息: 具体的处理流程和申诉机制
- 搜索关键词: ["处分流程", "学生申诉"]
- 继续探索: true

[KB检索] 关键词: 处分流程
找到 6 条相关信息:
- 流程: 通知学生 → 调查取证 → 听证 → 决定 → 送达

[推理]
处分流程包括通知、调查、听证、决定和送达五个步骤，
学生有权在收到处分后提出申诉。
```

**最终整合**:
```
【最终答案】

学校对学生旷课的处理流程:

一、旷课认定
- 定义: 未经批准缺席教学活动
- 统计: 按学时累计

二、处分标准
- 累计 10 学时: 警告处分
- 累计 20 学时: 严重警告
- 累计 40 学时: 退学处分

三、处理流程
1. 通知学生及家长
2. 调查核实旷课情况
3. 组织听证会（学生可辩护）
4. 学校作出处分决定
5. 送达处分文件

四、救济途径
- 学生可在收到处分后 10 日内提出申诉
- 申诉委员会在 15 日内作出复查决定
```

### 优缺点分析

#### ✅ 优点

1. **推理链完整**
   - 显式思考过程
   - 可追溯决策依据

2. **信息收集全面**
   - 多轮迭代
   - 主动探索缺失信息

3. **答案质量高**
   - 充分整合知识
   - 逻辑严谨

4. **可解释性强**
   - 展示推理步骤
   - 用户可理解决策过程

#### ❌ 缺点

1. **响应时间长**
   - 多轮迭代，每轮需 LLM 调用
   - 平均耗时 10-30 秒

2. **成本高**
   - 多次 LLM 调用
   - Token 消耗大

3. **可能过度探索**
   - 简单问题也可能多轮迭代
   - 需要智能停止机制

### 适用场景

✅ **适合**:
- 复杂研究性问题
- 需要深度推理
- 要求高质量答案
- 可接受较长等待时间

❌ **不适合**:
- 简单事实查询
- 实时对话
- 资源受限环境

---

## 5️⃣ FusionGraphRAGAgent - 多Agent协作

### 核心设计理念

**"像研究团队一样协作：Plan-Execute-Report 架构"**

FusionGraphRAGAgent 是最复杂的实现，通过多个专门化 Agent 协作完成研究任务。

### 技术架构

```
【Plan 阶段】Planning Team
    ├─ Clarifier: 澄清用户意图
    ├─ TaskDecomposer: 分解任务
    └─ PlanReviewer: 审查计划
    ↓
    生成 PlanSpec (任务图)
    ↓
【Execute 阶段】Execution Team
    ├─ WorkerCoordinator: 协调执行
    ├─ RetrievalExecutor: 检索任务
    ├─ ResearchExecutor: 研究任务
    └─ Reflector: 反思结果
    ↓
    生成 ExecutionRecords
    ↓
【Report 阶段】Reporting Team
    ├─ OutlineBuilder: 构建大纲
    ├─ SectionWriter: 写作章节 (Map-Reduce)
    ├─ ConsistencyChecker: 一致性检查
    └─ Formatter: 格式化输出
    ↓
    生成最终报告
```

### 关键代码实现

**文件**: `backend/graphrag_agent/agents/fusion_agent.py`

```python
class FusionGraphRAGAgent:
    """Fusion GraphRAG Agent - 多智能体编排"""

    def __init__(self, cache_dir: str = "./cache/fusion_graphrag"):
        self.cache_dir = cache_dir

        # 🔑 核心: 多智能体门面
        self.multi_agent = MultiAgentFacade()

        # 兼容接口
        self.memory = _MemoryShim()
        self.graph = _GraphShim()
        self.execution_log = []

        # 缓存
        self._global_cache = {}
        self._session_cache = {}

    def ask(self, query: str, thread_id: str = "default") -> str:
        """标准问答"""
        answer, _ = self._execute(query, thread_id)
        return answer

    def ask_with_trace(self, query: str, thread_id: str = "default") -> Dict:
        """带执行轨迹的问答"""
        answer, payload = self._execute(query, thread_id)
        return {
            "answer": answer,
            "payload": payload  # 包含完整的执行记录
        }

    def _execute(
        self,
        query: str,
        thread_id: str,
        assumptions: Optional[List[str]] = None,
        report_type: Optional[str] = None
    ) -> Tuple[str, Dict]:
        """
        执行查询

        步骤:
        1. 检查缓存
        2. 调用多智能体编排器
        3. 缓存结果
        4. 返回答案和执行记录
        """
        # 1. 缓存检查
        cached = self._read_cache(query, thread_id)
        if cached is not None:
            return cached, {"status": "cached"}

        # 2. 🔑 调用多智能体编排器
        payload = self.multi_agent.process_query(
            query.strip(),
            assumptions=assumptions,
            report_type=report_type
        )

        # 3. 提取答案
        answer = self._normalize_answer(payload.get("response"))

        # 4. 缓存结果
        self._write_cache(query, thread_id, answer)

        # 5. 记录执行日志
        self.execution_log = payload.get("execution_records", [])

        return answer, payload
```

### MultiAgentFacade 实现

**文件**: `backend/graphrag_agent/agents/multi_agent/integration/legacy_facade.py`

```python
class MultiAgentFacade:
    """多智能体门面 - 对外统一接口"""

    def __init__(self):
        # 🔑 初始化三个阶段的组件
        self.planner = self._create_planner()
        self.executor = self._create_executor()
        self.reporter = self._create_reporter()

    def process_query(
        self,
        query: str,
        assumptions: Optional[List[str]] = None,
        report_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理查询 - Plan-Execute-Report 流程

        返回:
        {
            "response": "最终报告",
            "plan": PlanSpec对象,
            "execution_records": [ExecutionRecord, ...],
            "outline": 报告大纲,
            "consistency_check": 一致性检查结果
        }
        """
        # ========== Plan 阶段 ==========
        print("【Plan 阶段】开始任务规划...")

        # 1. 澄清意图
        clarified_query = self.planner.clarify(query)

        # 2. 分解任务
        task_graph = self.planner.decompose(clarified_query)

        # 3. 审查计划
        plan_spec = self.planner.review(task_graph)

        print(f"生成计划: {len(plan_spec.tasks)} 个任务")

        # ========== Execute 阶段 ==========
        print("【Execute 阶段】执行任务...")

        # 4. 协调执行
        execution_records = self.executor.execute(plan_spec)

        print(f"完成执行: {len(execution_records)} 条记录")

        # ========== Report 阶段 ==========
        print("【Report 阶段】生成报告...")

        # 5. 构建大纲
        outline = self.reporter.build_outline(
            query=query,
            evidence=execution_records
        )

        # 6. 写作章节 (Map-Reduce)
        sections = self.reporter.write_sections(
            outline=outline,
            evidence=execution_records
        )

        # 7. 一致性检查
        consistency_result = self.reporter.check_consistency(
            sections=sections,
            evidence=execution_records
        )

        # 8. 格式化输出
        final_report = self.reporter.format(
            sections=sections,
            outline=outline
        )

        return {
            "response": final_report,
            "plan": plan_spec,
            "execution_records": execution_records,
            "outline": outline,
            "consistency_check": consistency_result
        }
```

### Planner 阶段详解

**文件**: `backend/graphrag_agent/agents/multi_agent/planner/task_decomposer.py`

```python
class TaskDecomposer:
    """任务分解器"""

    def decompose(self, query: str) -> PlanSpec:
        """
        将查询分解为任务图

        返回 PlanSpec:
        {
            "tasks": [
                {
                    "id": "task_1",
                    "type": "retrieval",  # 检索任务
                    "description": "检索学生管理规定",
                    "dependencies": []
                },
                {
                    "id": "task_2",
                    "type": "research",   # 研究任务
                    "description": "分析处分流程",
                    "dependencies": ["task_1"]
                },
                {
                    "id": "task_3",
                    "type": "synthesis",  # 综合任务
                    "description": "整合信息生成答案",
                    "dependencies": ["task_1", "task_2"]
                }
            ]
        }
        """
        prompt = f"""
        分析以下查询，分解为具体任务:

        查询: {query}

        任务类型:
        - retrieval: 检索相关文档
        - research: 深度研究特定主题
        - synthesis: 综合多个信息源

        返回 JSON 格式的任务图，包含任务ID、类型、描述和依赖关系。
        """

        result = self.llm.invoke(prompt)
        task_data = json.loads(result.content)

        return PlanSpec(tasks=task_data["tasks"])
```

### Executor 阶段详解

**文件**: `backend/graphrag_agent/agents/multi_agent/executor/worker_coordinator.py`

```python
class WorkerCoordinator:
    """工作协调器 - 按依赖关系执行任务"""

    def execute(self, plan_spec: PlanSpec) -> List[ExecutionRecord]:
        """
        执行任务图

        工作流程:
        1. 拓扑排序任务（按依赖关系）
        2. 逐个执行任务
        3. 记录执行结果
        """
        # 1. 拓扑排序
        sorted_tasks = self._topological_sort(plan_spec.tasks)

        execution_records = []

        # 2. 逐个执行
        for task in sorted_tasks:
            # 根据任务类型选择执行器
            if task["type"] == "retrieval":
                executor = self.retrieval_executor
            elif task["type"] == "research":
                executor = self.research_executor
            else:
                executor = self.synthesis_executor

            # 执行任务
            start_time = time.time()
            result = executor.execute(task)
            duration = time.time() - start_time

            # 记录执行结果
            record = ExecutionRecord(
                task_id=task["id"],
                task_type=task["type"],
                result=result,
                duration=duration,
                evidence=result.get("evidence", [])
            )

            execution_records.append(record)

            print(f"完成任务 {task['id']}: {duration:.2f}s")

        return execution_records
```

### Reporter 阶段详解

**文件**: `backend/graphrag_agent/agents/multi_agent/reporter/section_writer.py`

```python
class SectionWriter:
    """章节写作器 - Map-Reduce 模式"""

    def write_sections(
        self,
        outline: List[str],
        evidence: List[ExecutionRecord]
    ) -> List[str]:
        """
        写作报告章节

        Map-Reduce 流程:
        1. Map: 每个章节并行写作
        2. Reduce: 整合并优化
        """
        sections = []

        # Map 阶段: 并行写作每个章节
        for section_title in outline:
            # 提取相关证据
            relevant_evidence = self._filter_evidence(
                section_title,
                evidence
            )

            # 写作章节
            section_content = self._write_single_section(
                title=section_title,
                evidence=relevant_evidence
            )

            sections.append({
                "title": section_title,
                "content": section_content
            })

        # Reduce 阶段: 整合优化
        optimized_sections = self._optimize_sections(sections)

        return optimized_sections

    def _write_single_section(
        self,
        title: str,
        evidence: List
    ) -> str:
        """写作单个章节"""
        prompt = f"""
        写作报告章节:

        章节标题: {title}

        支持证据:
        {chr(10).join([e.summary for e in evidence])}

        要求:
        1. 内容详实、逻辑清晰
        2. 引用证据（使用 [1][2] 格式）
        3. 字数 500-1000 字
        """

        section_content = self.llm.invoke(prompt).content

        return section_content
```

### 完整执行示例

**查询**: "详细介绍学校的学生管理制度"

**Plan 阶段输出**:
```json
{
    "tasks": [
        {
            "id": "retrieve_regulations",
            "type": "retrieval",
            "description": "检索学生管理相关规章制度",
            "dependencies": []
        },
        {
            "id": "research_attendance",
            "type": "research",
            "description": "深入研究考勤管理制度",
            "dependencies": ["retrieve_regulations"]
        },
        {
            "id": "research_discipline",
            "type": "research",
            "description": "深入研究违纪处分制度",
            "dependencies": ["retrieve_regulations"]
        },
        {
            "id": "synthesize_report",
            "type": "synthesis",
            "description": "综合信息生成完整报告",
            "dependencies": ["research_attendance", "research_discipline"]
        }
    ]
}
```

**Execute 阶段输出**:
```python
execution_records = [
    ExecutionRecord(
        task_id="retrieve_regulations",
        result={
            "documents": [
                "学生管理规定.pdf",
                "考勤管理办法.docx",
                "违纪处分条例.pdf"
            ],
            "evidence": ["管理规定第1条...", "管理规定第2条..."]
        },
        duration=2.3
    ),
    ExecutionRecord(
        task_id="research_attendance",
        result={
            "findings": "考勤管理包括...",
            "evidence": ["考勤统计方式...", "请假流程..."]
        },
        duration=5.7
    ),
    # ...
]
```

**Report 阶段输出**:
```markdown
# 学校学生管理制度详解

## 一、总则

学生管理制度是学校规范化管理的重要组成部分[1]，旨在维护正常的教学秩序...[2]

## 二、考勤管理制度

### 2.1 考勤统计方式
学校采用电子考勤系统，按学时统计出勤情况[3]...

### 2.2 请假流程
学生因故不能参加教学活动，应提前办理请假手续[4]...

## 三、违纪处分制度

### 3.1 处分类型
根据违纪情节轻重，处分分为警告、严重警告、记过、留校察看、开除学籍五种[5]...

### 3.2 处理流程
1. 调查取证
2. 通知学生及家长
3. 组织听证会
4. 作出处分决定
5. 送达处分文件[6]

## 四、救济途径

学生对处分决定有异议的，可在收到处分后10日内向学校申诉委员会提出书面申诉[7]...

---

【参考文献】
[1] 学生管理规定.pdf, 第1条
[2] 学生管理规定.pdf, 第2条
[3] 考勤管理办法.docx, 第3.1节
...
```

### 优缺点分析

#### ✅ 优点

1. **专业化分工**
   - 每个 Agent 负责特定任务
   - 团队协作，质量高

2. **生成长篇报告**
   - Map-Reduce 模式
   - 支持数千字报告

3. **可追溯性强**
   - 完整的执行记录
   - 证据链清晰

4. **可扩展性好**
   - 易于添加新 Agent
   - 灵活的任务编排

#### ❌ 缺点

1. **极慢响应速度**
   - 多阶段处理
   - 平均耗时 30-120 秒

2. **成本极高**
   - 大量 LLM 调用
   - Token 消耗可达数万

3. **复杂度极高**
   - 代码量大
   - 调试困难

### 适用场景

✅ **适合**:
- 生成研究报告
- 深度分析任务
- 需要结构化输出
- 可接受长时间等待

❌ **不适合**:
- 实时对话
- 简单问答
- 资源受限环境

---

## 📊 性能对比

### 响应时间对比

| Agent 类型 | 平均响应时间 | LLM 调用次数 | Token 消耗 |
|-----------|------------|------------|-----------|
| **NaiveRagAgent** | 0.5-1s | 1-2 | ~1K |
| **HybridAgent** | 1-3s | 2-3 | ~2K |
| **GraphAgent** | 2-5s | 3-5 | ~3K |
| **DeepResearchAgent** | 10-30s | 10-30 | ~10K |
| **FusionGraphRAGAgent** | 30-120s | 50-200 | ~50K |

### 答案质量对比

| Agent 类型 | 准确性 | 完整性 | 结构化 | 可解释性 |
|-----------|-------|-------|-------|---------|
| **NaiveRagAgent** | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ |
| **HybridAgent** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **GraphAgent** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **DeepResearchAgent** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **FusionGraphRAGAgent** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🎯 选择指南

### 决策树

```
问题复杂度评估
    │
    ├─ 简单事实查询？
    │   └─ YES → NaiveRagAgent
    │
    ├─ 需要实时响应？
    │   └─ YES → HybridAgent
    │
    ├─ 需要图结构信息？
    │   └─ YES → GraphAgent
    │
    ├─ 复杂推理问题？
    │   └─ YES → DeepResearchAgent
    │
    └─ 需要长篇报告？
        └─ YES → FusionGraphRAGAgent
```

### 使用建议

**默认选择**: **HybridAgent**
- 平衡速度和质量
- 适用于 80% 的场景

**特殊场景**:
- **快速原型**: NaiveRagAgent
- **知识图谱查询**: GraphAgent
- **研究性问题**: DeepResearchAgent
- **生成报告**: FusionGraphRAGAgent

---

## 📝 总结

### 核心特点

| Agent | 核心特点 | 一句话总结 |
|-------|---------|-----------|
| **NaiveRagAgent** | 简单快速 | 基础向量检索，快速原型 |
| **HybridAgent** | 平衡性好 | 混合检索，默认首选 |
| **GraphAgent** | 图结构 | 利用图结构，支持聚合 |
| **DeepResearchAgent** | 多轮推理 | 像研究员思考，质量最高 |
| **FusionGraphRAGAgent** | 团队协作 | 多Agent编排，生成报告 |

### 技术创新点

1. **NaiveRag**: 轻量化设计
2. **Hybrid**: 双层关键词提取
3. **Graph**: Map-Reduce 聚合
4. **DeepResearch**: Chain of Exploration
5. **Fusion**: Plan-Execute-Report 架构

---

**文档版本**: v1.0
**创建时间**: 2025-12-29
**作者**: Claude Code
**相关文档**:
- `docs/Chat工作台完整调用流程.md`
- `docs/Python面向对象_Agent调用机制详解.md`

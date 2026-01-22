import time
import os
import concurrent.futures
from typing import List, Tuple
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)

from graphrag_agent.graph.core import retry
from graphrag_agent.config.settings import MAX_WORKERS as DEFAULT_MAX_WORKERS, BATCH_SIZE as DEFAULT_BATCH_SIZE

class EntityRelationExtractor:
    """
    实体关系提取器，负责从文本中提取实体和关系。
    使用LLM分析文本块，生成结构化的实体和关系数据。
    """
    
    def __init__(self, llm, system_template, human_template, 
             entity_types: List[str], relationship_types: List[str],
             max_workers=4, batch_size=5):
        """
        初始化实体关系提取器
        
        Args:
            llm: 语言模型
            system_template: 系统提示模板
            human_template: 用户提示模板
            entity_types: 实体类型列表
            relationship_types: 关系类型列表
            max_workers: 并行工作线程数
            batch_size: 批处理大小
        """
        self.llm = llm
        self.entity_types = entity_types
        self.relationship_types = relationship_types
        self.chat_history = []
        
        # 设置分隔符
        self.tuple_delimiter = " : "
        self.record_delimiter = "\n"
        self.completion_delimiter = "\n\n"
        
        # 创建提示模板
        system_message_prompt = SystemMessagePromptTemplate.from_template(system_template)
        human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)
        
        self.chat_prompt = ChatPromptTemplate.from_messages([
            system_message_prompt,
            MessagesPlaceholder("chat_history"),
            human_message_prompt
        ])
        
        # 创建处理链
        self.chain = self.chat_prompt | self.llm
        
        # 并行处理配置
        self.max_workers = max_workers or DEFAULT_MAX_WORKERS
        self.batch_size = batch_size or DEFAULT_BATCH_SIZE
        
    def process_chunks(self, file_contents: List[Tuple], progress_callback=None) -> List[Tuple]:
        """
        并行处理所有文件的所有chunks
        
        Args:
            file_contents: 文件内容列表
            progress_callback: 进度回调函数
            
        Returns:
            List[Tuple]: 处理结果
        """
        t0 = time.time()
        chunk_index = 0
        total_chunks = sum(len(file_content[2]) for file_content in file_contents)
        
        for i, file_content in enumerate(file_contents):
            chunks = file_content[2]

            results: list[str] = [""] * len(chunks)
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_chunk = {
                    executor.submit(self._process_single_chunk, "".join(chunks[idx])): idx
                    for idx in range(len(chunks))
                }
                for future in concurrent.futures.as_completed(future_to_chunk):
                    chunk_idx = future_to_chunk[future]
                    try:
                        results[chunk_idx] = future.result()
                    except Exception as exc:
                        print(f"Chunk {chunk_idx} 处理异常: {exc}")
                        retry_count = 0
                        while retry_count < 3:
                            try:
                                print(f"尝试重试 Chunk {chunk_idx}, 第 {retry_count+1} 次")
                                results[chunk_idx] = self._process_single_chunk("".join(chunks[chunk_idx]))
                                break
                            except Exception as retry_exc:
                                print(f"重试失败: {retry_exc}")
                                retry_count += 1
                                time.sleep(1)
                        if not results[chunk_idx]:
                            results[chunk_idx] = ""

                    if progress_callback:
                        progress_callback(chunk_index)
                    chunk_index += 1

            file_content.append(results)
            print(f"文件 {i+1}/{len(file_contents)} 处理完成")
        
        process_time = time.time() - t0
        print(f"所有chunks处理完成, 总耗时: {process_time:.2f}秒, 平均每chunk: {process_time/total_chunks:.2f}秒")
        return file_contents
    
    def process_chunks_batch(self, file_contents: List[Tuple], progress_callback=None) -> List[Tuple]:
        """
        批量处理chunks，减少LLM调用次数
        
        Args:
            file_contents: 文件内容列表
            progress_callback: 进度回调函数
            
        Returns:
            List[Tuple]: 处理结果
        """
        for file_content in file_contents:
            chunks = file_content[2]
            results = []
            
            # 智能动态批处理大小
            chunk_lengths = [len(''.join(chunk)) for chunk in chunks]
            avg_chunk_size = sum(chunk_lengths) / len(chunk_lengths) if chunk_lengths else 0
            
            # 根据平均chunk大小动态调整批处理大小
            dynamic_batch_size = max(1, min(self.batch_size, int(10000 / (avg_chunk_size + 1))))
            
            # 按批次处理
            for i in range(0, len(chunks), dynamic_batch_size):
                batch_chunks = chunks[i:i+dynamic_batch_size]
                
                # 准备批处理输入
                batch_inputs = []
                for chunk in batch_chunks:
                    batch_inputs.append(''.join(chunk))
                
                # 使用分隔符合并多个文本块
                batch_text = f"\n{'-'*50}\n".join(batch_inputs)
                
                try:
                    # 使用原始提示模板处理批量输入
                    batch_response = self.chain.invoke({
                        "chat_history": self.chat_history,
                        "entity_types": self.entity_types,
                        "relationship_types": self.relationship_types,
                        "tuple_delimiter": self.tuple_delimiter,
                        "record_delimiter": self.record_delimiter,
                        "completion_delimiter": self.completion_delimiter,
                        "input_text": batch_text
                    })
                    
                    # 解析批量响应
                    batch_results = self._parse_batch_response(batch_response.content)
                    
                    # 处理结果数量不匹配的情况
                    if len(batch_results) != len(batch_chunks):
                        batch_results = []
                        for idx, chunk in enumerate(batch_chunks):
                            individual_result = self._process_single_chunk(''.join(chunk))
                            batch_results.append(individual_result)
                    
                    results.extend(batch_results)
                except Exception as e:
                    print(f"批处理错误，切换到单个处理: {e}")
                    for idx, chunk in enumerate(batch_chunks):
                        try:
                            individual_result = self._process_single_chunk(''.join(chunk))
                            results.append(individual_result)
                        except Exception as e2:
                            print(f"单个chunk处理失败: {e2}")
                            results.append("")
                
                # 更新进度
                if progress_callback:
                    for j in range(len(batch_chunks)):
                        progress_callback(i + j)
            
            file_content.append(results)
        
        return file_contents

    def _parse_batch_response(self, batch_content: str) -> List[str]:
        """
        解析批量响应，将其分割为单独的结果
        
        Args:
            batch_content: 批处理响应内容
            
        Returns:
            List[str]: 分割后的结果列表
        """
        # 使用分隔符分割响应
        parts = batch_content.split(f"\n{'-'*50}\n")
        return [part.strip() for part in parts]
    
    @retry(times=3, exceptions=(Exception,), delay=1.0)
    def _process_single_chunk(self, input_text: str) -> str:
        """
        处理单个文本块
        
        Args:
            input_text: 输入文本
            
        Returns:
            str: 处理结果
        """
        # 调用LLM处理
        response = self.chain.invoke({
            "chat_history": self.chat_history,
            "entity_types": self.entity_types,
            "relationship_types": self.relationship_types,
            "tuple_delimiter": self.tuple_delimiter,
            "record_delimiter": self.record_delimiter,
            "completion_delimiter": self.completion_delimiter,
            "input_text": input_text
        })
        
        result = response.content
        return result
    
    def stream_process_large_files(self, file_path: str, chunk_size: int = 5000, 
                                   structure_builder=None, graph_writer=None) -> None:
        """
        以流式方式处理大文件，避免一次性加载全部内容
        
        Args:
            file_path: 文件路径
            chunk_size: 块大小
            structure_builder: 结构构建器
            graph_writer: 图写入器
        """
        if not structure_builder or not graph_writer:
            print("需要提供structure_builder和graph_writer才能进行流式处理")
            return
            
        def text_chunks_iterator(file_path, chunk_size):
            with open(file_path, 'r', encoding='utf-8') as f:
                chunk = []
                chars_count = 0
                for line in f:
                    chunk.append(line)
                    chars_count += len(line)
                    if chars_count >= chunk_size:
                        yield chunk
                        chunk = []
                        chars_count = 0
                if chunk:  # 不要忘记最后一个可能不满的chunk
                    yield chunk
        
        # 处理文件的元数据
        file_name = os.path.basename(file_path)
        file_type = os.path.splitext(file_name)[1]
        
        # 创建文档节点
        structure_builder.create_document(
            type=file_type,
            uri=file_path,
            file_name=file_name,
            domain="document"
        )
        
        # 流式处理文件
        chunks = []
        for chunk in text_chunks_iterator(file_path, chunk_size):
            chunks.append(chunk)
        
        # 创建chunk之间的关系
        chunks_with_hash = structure_builder.create_relation_between_chunks(
            file_name, chunks
        )
        
        # 并行处理所有chunks
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 创建任务
            future_to_chunk = {}
            for chunk_data in chunks_with_hash:
                chunk_text = chunk_data['chunk_doc'].page_content
                future = executor.submit(self._process_single_chunk, chunk_text)
                future_to_chunk[future] = chunk_data
            
            # 处理结果并写入图数据库
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk_data = future_to_chunk[future]
                try:
                    result = future.result()
                    
                    # 实时写入一个chunk的结果到图数据库
                    graph_document = graph_writer.convert_to_graph_document(
                        chunk_data['chunk_id'],
                        chunk_data['chunk_doc'].page_content,
                        result
                    )
                    
                    if len(graph_document.nodes) > 0 or len(graph_document.relationships) > 0:
                        graph_writer.write_graph_documents([graph_document])
                        
                except Exception as exc:
                    print(f"处理chunk {chunk_data['chunk_id']} 时发生错误: {exc}")

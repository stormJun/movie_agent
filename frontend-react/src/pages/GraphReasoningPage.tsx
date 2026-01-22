import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
} from "antd";
import { useState } from "react";
import type { KnowledgeGraphLink, KnowledgeGraphNode } from "../types/graph";
import type { KgReasoningRequest } from "../types/graph";
import { kgReasoning } from "../services/graph";
import { KnowledgeGraphPanel } from "../components/KnowledgeGraphPanel";

function extractNodesLinks(payload: unknown): { nodes: KnowledgeGraphNode[]; links: KnowledgeGraphLink[] } {
  if (!payload || typeof payload !== "object") return { nodes: [], links: [] };
  const obj = payload as Record<string, unknown>;
  const nodes = Array.isArray(obj.nodes) ? (obj.nodes as KnowledgeGraphNode[]) : [];
  const links = Array.isArray(obj.links) ? (obj.links as KnowledgeGraphLink[]) : [];
  return { nodes, links };
}

const reasoningTypeOptions = [
  { label: "最短路径 shortest_path", value: "shortest_path" },
  { label: "一到两跳 one_two_hop", value: "one_two_hop" },
  { label: "共同邻居 common_neighbors", value: "common_neighbors" },
  { label: "所有路径 all_paths", value: "all_paths" },
  { label: "实体环 entity_cycles", value: "entity_cycles" },
  { label: "实体影响力 entity_influence", value: "entity_influence" },
  { label: "社区检测 entity_community", value: "entity_community" },
];

export function GraphReasoningPage() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [form] = Form.useForm<KgReasoningRequest>();
  const reasoningType = Form.useWatch("reasoning_type", form);

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      const values = (await form.validateFields()) as KgReasoningRequest;
      const resp = await kgReasoning(values);
      setData(resp);
      if (typeof resp.error === "string" && resp.error) setError(resp.error);
    } catch (e) {
      setError(e instanceof Error ? e.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }

  const { nodes, links } = extractNodesLinks(data);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card title="图谱推理（/api/v1/kg_reasoning）">
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            reasoning_type: "shortest_path",
            entity_a: "",
            entity_b: "",
            max_depth: 3,
          }}
        >
          <Form.Item
            name="reasoning_type"
            label="reasoning_type"
            rules={[{ required: true, message: "请选择推理类型" }]}
          >
            <Select options={reasoningTypeOptions} />
          </Form.Item>

          <Form.Item
            name="entity_a"
            label="entity_a"
            rules={[{ required: true, message: "请输入实体 A" }]}
          >
            <Input placeholder="实体ID（e.id）" />
          </Form.Item>

          {["shortest_path", "one_two_hop", "common_neighbors", "all_paths"].includes(
            String(reasoningType),
          ) ? (
            <Form.Item
              name="entity_b"
              label="entity_b"
              rules={[{ required: true, message: "请输入实体 B" }]}
            >
              <Input placeholder="实体ID（e.id）" />
            </Form.Item>
          ) : (
            <Form.Item name="entity_b" label="entity_b（可选）">
              <Input placeholder="可选" />
            </Form.Item>
          )}

          <Form.Item name="max_depth" label="max_depth">
            <InputNumber min={1} max={5} />
          </Form.Item>

          {reasoningType === "entity_community" ? (
            <Form.Item name="algorithm" label="algorithm（可选）">
              <Select
                options={[
                  { label: "leiden", value: "leiden" },
                  { label: "sllpa", value: "sllpa" },
                ]}
              />
            </Form.Item>
          ) : null}

          <Form.Item>
            <Button type="primary" onClick={submit} loading={loading}>
              执行推理
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="结果">
        <KnowledgeGraphPanel nodes={nodes} links={links} raw={data} error={error} />
      </Card>
    </Space>
  );
}

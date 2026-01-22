import { Button, Card, Col, Form, Input, InputNumber, Row, Space } from "antd";
import { useState } from "react";
import type { KnowledgeGraphResponse } from "../types/graph";
import { getKnowledgeGraph, getKnowledgeGraphFromMessage } from "../services/graph";
import { KnowledgeGraphPanel } from "../components/KnowledgeGraphPanel";

export function GraphExplorePage() {
  const [loadingGlobal, setLoadingGlobal] = useState(false);
  const [globalGraph, setGlobalGraph] = useState<KnowledgeGraphResponse | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const [loadingExtracted, setLoadingExtracted] = useState(false);
  const [extractedGraph, setExtractedGraph] = useState<KnowledgeGraphResponse | null>(null);
  const [extractedError, setExtractedError] = useState<string | null>(null);

  const [globalForm] = Form.useForm<{ limit: number; query?: string }>();
  const [extractForm] = Form.useForm<{ message?: string; query?: string }>();

  async function loadGlobal() {
    setLoadingGlobal(true);
    setGlobalError(null);
    try {
      const values = globalForm.getFieldsValue();
      const resp = await getKnowledgeGraph({ limit: values.limit, query: values.query });
      if (resp.error) setGlobalError(resp.error);
      setGlobalGraph(resp);
    } catch (e) {
      setGlobalError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoadingGlobal(false);
    }
  }

  async function loadExtracted() {
    setLoadingExtracted(true);
    setExtractedError(null);
    try {
      const values = extractForm.getFieldsValue();
      const resp = await getKnowledgeGraphFromMessage({ message: values.message, query: values.query });
      if (resp.error) setExtractedError(resp.error);
      setExtractedGraph(resp);
    } catch (e) {
      setExtractedError(e instanceof Error ? e.message : "解析失败");
    } finally {
      setLoadingExtracted(false);
    }
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card title="全局图谱（/api/v1/knowledge_graph）">
        <Form
          form={globalForm}
          layout="inline"
          initialValues={{ limit: 100, query: "" }}
          onFinish={loadGlobal}
        >
          <Form.Item name="limit" label="limit">
            <InputNumber min={1} max={5000} />
          </Form.Item>
          <Form.Item name="query" label="query" style={{ minWidth: 360 }}>
            <Input placeholder="可选：按 id/description 模糊过滤" allowClear />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loadingGlobal}>
              加载
            </Button>
          </Form.Item>
        </Form>
        <div style={{ marginTop: 16 }}>
          <KnowledgeGraphPanel
            nodes={globalGraph?.nodes ?? []}
            links={globalGraph?.links ?? []}
            raw={globalGraph}
            error={globalError}
          />
        </div>
      </Card>

      <Card title="从回答/文本提取图谱（/api/v1/knowledge_graph_from_message）">
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Form
              form={extractForm}
              layout="vertical"
              initialValues={{ message: "", query: "" }}
              onFinish={loadExtracted}
            >
              <Form.Item name="message" label="message">
                <Input.TextArea
                  autoSize={{ minRows: 4, maxRows: 10 }}
                  placeholder="粘贴一段回答或包含 Entities/Relationships/Chunks 的文本"
                />
              </Form.Item>
              <Form.Item name="query" label="query（可选）">
                <Input allowClear />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={loadingExtracted}>
                  解析
                </Button>
              </Form.Item>
            </Form>
          </Col>
        </Row>

        <KnowledgeGraphPanel
          nodes={extractedGraph?.nodes ?? []}
          links={extractedGraph?.links ?? []}
          raw={extractedGraph}
          error={extractedError}
        />
      </Card>
    </Space>
  );
}

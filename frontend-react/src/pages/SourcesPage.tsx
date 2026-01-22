import {
  Alert,
  Button,
  Card,
  Drawer,
  Form,
  InputNumber,
  Modal,
  Row,
  Col,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import type { ColumnsType } from "antd/es/table";
import type { Chunk } from "../types/source";
import { getChunks, getSourceContent, getSourceInfoBatch } from "../services/source";

function snippet(text?: string, maxLen = 160): string {
  if (!text) return "";
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= maxLen) return clean;
  return `${clean.slice(0, maxLen)}…`;
}

export function SourcesPage() {
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTitle, setDrawerTitle] = useState<string>("");
  const [drawerContent, setDrawerContent] = useState<string>("");
  const [drawerLoading, setDrawerLoading] = useState(false);

  // 批量查看相关状态
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [batchContents, setBatchContents] = useState<Record<string, string>>({});
  const [batchLoading, setBatchLoading] = useState(false);
  const [sourceInfoMap, setSourceInfoMap] = useState<Record<string, string>>({});

  const [form] = Form.useForm<{ limit: number; offset: number }>();

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const values = form.getFieldsValue();
      const resp = await getChunks({ limit: values.limit, offset: values.offset });
      if (resp.error) setError(resp.error);
      setChunks(resp.chunks || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  // 批量查看选中内容
  async function handleBatchView() {
    if (selectedRowKeys.length === 0) {
      message.warning("请先选择要查看的内容");
      return;
    }

    setBatchModalOpen(true);
    setBatchLoading(true);

    try {
      // 批量获取源内容
      const contents: Record<string, string> = {};
      const ids = selectedRowKeys as string[];

      // 先获取文件名信息
      try {
        const infoMap = await getSourceInfoBatch(ids);
        const next: Record<string, string> = {};
        for (const [k, v] of Object.entries(infoMap)) {
          next[k] = v?.file_name || k;
        }
        setSourceInfoMap(next);
      } catch {
        // 忽略批量获取失败，使用ID作为显示
      }

      // 逐个获取内容（并发）
      await Promise.all(
        ids.map(async (id) => {
          try {
            const resp = await getSourceContent(id);
            contents[id] = resp.content || "";
          } catch {
            contents[id] = "(获取失败)";
          }
        })
      );

      setBatchContents(contents);
    } catch (e) {
      message.error(e instanceof Error ? e.message : "批量加载失败");
    } finally {
      setBatchLoading(false);
    }
  }

  useEffect(() => {
    form.setFieldsValue({ limit: 20, offset: 0 });
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const columns: ColumnsType<Chunk> = useMemo(
    () => [
      { title: "fileName", dataIndex: "fileName", width: 260, ellipsis: true },
      { title: "id", dataIndex: "id", width: 260, ellipsis: true },
      {
        title: "text",
        dataIndex: "text",
        ellipsis: true,
        render: (_, row) => snippet(row.text),
      },
      {
        title: "操作",
        key: "actions",
        width: 120,
        render: (_, row) => (
          <Button
            size="small"
            onClick={async () => {
              setDrawerOpen(true);
              setDrawerTitle(row.fileName ? `${row.fileName}` : row.id);
              setDrawerLoading(true);
              try {
                const resp = await getSourceContent(row.id);
                setDrawerContent(resp.content || "");
              } catch (e) {
                message.error(e instanceof Error ? e.message : "获取内容失败");
                setDrawerContent("");
              } finally {
                setDrawerLoading(false);
              }
            }}
          >
            查看
          </Button>
        ),
      },
    ],
    [],
  );

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card title="源内容 / Chunks（/api/v1/chunks + /api/v1/source）">
        <Form
          form={form}
          layout="inline"
          initialValues={{ limit: 20, offset: 0 }}
          onFinish={load}
        >
          <Form.Item name="limit" label="limit">
            <InputNumber min={1} max={200} />
          </Form.Item>
          <Form.Item name="offset" label="offset">
            <InputNumber min={0} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>
              刷新
            </Button>
          </Form.Item>
        </Form>

        <div style={{ marginTop: 16 }}>
          {error ? <Alert type="error" message={error} /> : null}
          <Space style={{ marginBottom: 8 }}>
            <Button
              type="primary"
              onClick={handleBatchView}
              disabled={selectedRowKeys.length === 0}
              loading={batchLoading}
            >
              批量查看 ({selectedRowKeys.length})
            </Button>
            <Button onClick={() => setSelectedRowKeys([])} disabled={selectedRowKeys.length === 0}>
              清除选择
            </Button>
          </Space>
          <Table
            size="small"
            rowKey={(row) => row.id}
            loading={loading}
            dataSource={chunks}
            columns={columns}
            pagination={{ pageSize: 10 }}
            rowSelection={{
              selectedRowKeys,
              onChange: setSelectedRowKeys,
            }}
          />
          <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
            注意：后端当前 `total` 不是全量计数，分页建议用 limit/offset 手动翻页。
          </Typography.Paragraph>
        </div>
      </Card>

      <Drawer
        title={drawerTitle}
        open={drawerOpen}
        width={720}
        onClose={() => setDrawerOpen(false)}
      >
        {drawerLoading ? (
          <Alert message="加载中..." type="info" />
        ) : (
          <pre style={{ whiteSpace: "pre-wrap" }}>{drawerContent}</pre>
        )}
      </Drawer>

      <Modal
        title={`批量查看源内容 (${selectedRowKeys.length} 项)`}
        open={batchModalOpen}
        onCancel={() => setBatchModalOpen(false)}
        footer={null}
        width={1200}
      >
        {batchLoading ? (
          <Alert message="正在加载内容..." type="info" />
        ) : (
          <Tabs
            defaultActiveKey={selectedRowKeys[0] as string}
            items={selectedRowKeys.map((key) => {
              const id = key as string;
              const fileName = sourceInfoMap[id] || id;
              return {
                key: id,
                label: (
                  <div style={{ maxWidth: 200 }}>
                    <Tag color="blue">{fileName}</Tag>
                  </div>
                ),
                children: (
                  <div>
                    <Row gutter={[8, 8]} style={{ marginBottom: 12 }}>
                      <Col span={24}>
                        <Space>
                          <Typography.Text strong>ID:</Typography.Text>
                          <Typography.Text code>{id}</Typography.Text>
                          {fileName !== id ? (
                            <>
                              <Typography.Text strong>文件名:</Typography.Text>
                              <Typography.Text>{fileName}</Typography.Text>
                            </>
                          ) : null}
                        </Space>
                      </Col>
                    </Row>
                    <div
                      style={{
                        maxHeight: "60vh",
                        overflow: "auto",
                        padding: 12,
                        background: "#f5f5f5",
                        borderRadius: 6,
                      }}
                    >
                      <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                        {batchContents[id] || "(暂无内容)"}
                      </pre>
                    </div>
                  </div>
                ),
              };
            })}
          />
        )}
      </Modal>
    </Space>
  );
}

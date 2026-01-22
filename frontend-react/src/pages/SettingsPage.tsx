import { Alert, Button, Card, Form, Input, Space, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { getApiBaseUrl, setApiBaseUrl } from "../app/settings";

export function SettingsPage() {
  const [form] = Form.useForm<{ apiBaseUrl: string }>();
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; detail: string } | null>(null);

  useEffect(() => {
    form.setFieldsValue({ apiBaseUrl: getApiBaseUrl() });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form]);

  async function save() {
    const values = await form.validateFields();
    setApiBaseUrl(values.apiBaseUrl);
    setTestResult(null);
    message.success("已保存（刷新页面后对所有请求生效）");
  }

  async function testConnection() {
    const values = await form.validateFields();
    const baseUrl = values.apiBaseUrl.trim();
    setTesting(true);
    setTestResult(null);
    try {
      const url = baseUrl.endsWith("/") ? `${baseUrl}openapi.json` : `${baseUrl}/openapi.json`;
      const resp = await fetch(url, { method: "GET" });
      const text = await resp.text();
      if (!resp.ok) {
        setTestResult({ ok: false, detail: `${resp.status} ${text.slice(0, 300)}` });
      } else {
        setTestResult({ ok: true, detail: text.slice(0, 300) });
      }
    } catch (e) {
      setTestResult({ ok: false, detail: e instanceof Error ? e.message : "请求失败" });
    } finally {
      setTesting(false);
    }
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card title="API 设置">
        <Typography.Paragraph type="secondary">
          React 前端默认使用 Vite 代理（`/api`）。如果你要直连后端，可在这里设置
          `VITE_API_BASE_URL` 对应的值（例如 `http://localhost:8324` 或 `http://127.0.0.1:8324`）。
        </Typography.Paragraph>

        <Form form={form} layout="vertical" initialValues={{ apiBaseUrl: getApiBaseUrl() }}>
          <Form.Item
            name="apiBaseUrl"
            label="API Base URL"
            rules={[{ required: true, message: "请输入 API Base URL" }]}
          >
            <Input placeholder="例如：http://localhost:8324" />
          </Form.Item>
          <Space>
            <Button type="primary" onClick={save}>
              保存
            </Button>
            <Button onClick={testConnection} loading={testing}>
              测试连接（GET /openapi.json）
            </Button>
          </Space>
        </Form>

        {testResult ? (
          <div style={{ marginTop: 16 }}>
            <Alert
              type={testResult.ok ? "success" : "error"}
              message={testResult.ok ? "连接正常" : "连接失败"}
              description={<pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{testResult.detail}</pre>}
              showIcon
            />
          </div>
        ) : null}
      </Card>
    </Space>
  );
}

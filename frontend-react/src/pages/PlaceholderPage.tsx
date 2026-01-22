import { Card, Typography } from "antd";

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <Card>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        {title}
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
        该页面尚未实现。先完成 Chat 与基础布局，后续按模块逐步迁移 Streamlit 的图谱与管理能力。
      </Typography.Paragraph>
    </Card>
  );
}


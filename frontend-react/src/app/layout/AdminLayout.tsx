import { Layout, Menu, Typography, Button } from "antd";
import {
  CommentOutlined,
  ApartmentOutlined,
  DeploymentUnitOutlined,
  ClusterOutlined,
  LinkOutlined,
  FileSearchOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from "@ant-design/icons";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: "/chat", icon: <CommentOutlined />, label: "Chat 工作台" },
  {
    key: "/graph",
    icon: <ApartmentOutlined />,
    label: "知识图谱",
    children: [
      { key: "/graph/explore", icon: <DeploymentUnitOutlined />, label: "探索" },
      { key: "/graph/reasoning", icon: <ClusterOutlined />, label: "推理" },
      { key: "/graph/manage/entities", icon: <ClusterOutlined />, label: "实体管理" },
      { key: "/graph/manage/relations", icon: <LinkOutlined />, label: "关系管理" },
    ],
  },
  { key: "/sources", icon: <FileSearchOutlined />, label: "源内容" },
  { key: "/settings", icon: <SettingOutlined />, label: "设置" },
];

function computeSelectedKeys(pathname: string): string[] {
  if (pathname.startsWith("/graph/manage/entities")) return ["/graph/manage/entities"];
  if (pathname.startsWith("/graph/manage/relations")) return ["/graph/manage/relations"];
  if (pathname.startsWith("/graph/explore")) return ["/graph/explore"];
  if (pathname.startsWith("/graph/reasoning")) return ["/graph/reasoning"];
  if (pathname.startsWith("/graph")) return ["/graph/explore"];
  return [pathname];
}

function computeOpenKeys(pathname: string): string[] {
  if (pathname.startsWith("/graph")) return ["/graph"];
  return [];
}

export function AdminLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [openKeys, setOpenKeys] = useState<string[]>(() =>
    computeOpenKeys(location.pathname),
  );

  useEffect(() => {
    setOpenKeys(computeOpenKeys(location.pathname));
  }, [location.pathname]);

  const [collapsed, setCollapsed] = useState(false);

  return (
    <Layout className="app-shell">
      <Sider
        width={240}
        theme="light"
        collapsible
        collapsed={collapsed}
        onCollapse={(val) => setCollapsed(val)}
        trigger={null}
      >
        <div style={{ padding: 16, textAlign: "center" }}>
          <Typography.Title level={5} style={{ margin: 0, whiteSpace: "nowrap", overflow: "hidden" }}>
            {collapsed ? "G" : "GraphRAG Console"}
          </Typography.Title>
          {!collapsed && <Typography.Text type="secondary">React Admin</Typography.Text>}
        </div>
        <Menu
          mode="inline"
          items={menuItems}
          selectedKeys={computeSelectedKeys(location.pathname)}
          openKeys={openKeys}
          onOpenChange={(keys) => setOpenKeys(keys as string[])}
          onClick={(e) => navigate(e.key)}
        />
      </Sider>

      <Layout>
        <Header style={{ background: "#fff", padding: "0 16px", display: "flex", alignItems: "center" }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{
              fontSize: "16px",
              width: 64,
              height: 64,
              marginRight: 16,
            }}
          />
          <Typography.Text strong>后端管理控制台</Typography.Text>
        </Header>
        <Content className="page">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

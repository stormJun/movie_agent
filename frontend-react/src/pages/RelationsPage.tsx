import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Table,
  Tabs,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import type { ColumnsType } from "antd/es/table";
import type { RelationData, RelationSearchFilter, RelationUpdateData } from "../types/management";
import {
  createRelation,
  deleteRelation,
  getRelationTypes,
  searchRelations,
  updateRelation,
} from "../services/management";

export function RelationsPage() {
  const [relationTypes, setRelationTypes] = useState<string[]>([]);
  const [loadingTypes, setLoadingTypes] = useState(false);

  const [relations, setRelations] = useState<RelationData[]>([]);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [searchForm] = Form.useForm<RelationSearchFilter>();
  const [createForm] = Form.useForm<RelationData>();
  const [updateForm] = Form.useForm<RelationUpdateData>();
  const [deleteForm] = Form.useForm<{ source: string; type: string; target: string }>();

  useEffect(() => {
    (async () => {
      setLoadingTypes(true);
      try {
        const types = await getRelationTypes();
        setRelationTypes(types);
      } catch (e) {
        message.error(e instanceof Error ? e.message : "获取关系类型失败");
      } finally {
        setLoadingTypes(false);
      }
    })();
  }, []);

  async function doSearch() {
    setLoadingSearch(true);
    setSearchError(null);
    try {
      const values = searchForm.getFieldsValue();
      const resp = await searchRelations(values);
      setRelations(resp);
    } catch (e) {
      setSearchError(e instanceof Error ? e.message : "查询失败");
    } finally {
      setLoadingSearch(false);
    }
  }

  const columns: ColumnsType<RelationData> = useMemo(
    () => [
      { title: "source", dataIndex: "source", width: 220, ellipsis: true },
      { title: "type", dataIndex: "type", width: 180, ellipsis: true },
      { title: "target", dataIndex: "target", width: 220, ellipsis: true },
      { title: "weight", dataIndex: "weight", width: 120 },
      { title: "description", dataIndex: "description", ellipsis: true },
    ],
    [],
  );

  async function submitCreate() {
    const values = (await createForm.validateFields()) as RelationData;
    const resp = await createRelation(values);
    if (!resp.success) {
      message.error(resp.message || "创建失败");
      return;
    }
    message.success("创建成功");
    await doSearch();
  }

  async function submitUpdate() {
    const values = (await updateForm.validateFields()) as RelationUpdateData;
    const resp = await updateRelation(values);
    if (!resp.success) {
      message.error(resp.message || "更新失败");
      return;
    }
    message.success("更新成功");
    await doSearch();
  }

  async function submitDelete() {
    const values = (await deleteForm.validateFields()) as {
      source: string;
      type: string;
      target: string;
    };
    const resp = await deleteRelation(values);
    if (!resp.success) {
      message.error(resp.message || "删除失败");
      return;
    }
    message.success("删除成功");
    await doSearch();
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card title="关系管理（CRUD）">
        <Tabs
          items={[
            {
              key: "search",
              label: "查询",
              children: (
                <Space direction="vertical" style={{ width: "100%" }} size="middle">
                  <Form
                    form={searchForm}
                    layout="inline"
                    initialValues={{ source: "", target: "", type: undefined, limit: 100 }}
                    onFinish={doSearch}
                  >
                    <Form.Item name="source" label="source">
                      <Input placeholder="实体ID" allowClear style={{ width: 220 }} />
                    </Form.Item>
                    <Form.Item name="target" label="target">
                      <Input placeholder="实体ID" allowClear style={{ width: 220 }} />
                    </Form.Item>
                    <Form.Item name="type" label="type">
                      <Select
                        allowClear
                        loading={loadingTypes}
                        style={{ width: 220 }}
                        options={relationTypes.map((t) => ({ label: t, value: t }))}
                      />
                    </Form.Item>
                    <Form.Item name="limit" label="limit">
                      <InputNumber min={1} max={5000} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={loadingSearch}>
                        查询
                      </Button>
                    </Form.Item>
                  </Form>

                  {searchError ? <Alert type="error" message={searchError} /> : null}
                  <Table
                    size="small"
                    rowKey={(row) => `${row.source}-${row.type}-${row.target}`}
                    dataSource={relations}
                    loading={loadingSearch}
                    columns={columns}
                    pagination={{ pageSize: 10 }}
                    onRow={(row) => ({
                      onClick: () => {
                        updateForm.setFieldsValue({
                          source: row.source,
                          target: row.target,
                          original_type: row.type,
                          new_type: row.type,
                          description: row.description,
                          weight: row.weight,
                        });
                        deleteForm.setFieldsValue({
                          source: row.source,
                          target: row.target,
                          type: row.type,
                        });
                      },
                    })}
                  />
                </Space>
              ),
            },
            {
              key: "create",
              label: "创建",
              children: (
                <Form
                  form={createForm}
                  layout="vertical"
                  initialValues={{
                    source: "",
                    type: "",
                    target: "",
                    description: "",
                    weight: 0.5,
                  }}
                  onFinish={submitCreate}
                >
                  <Form.Item name="source" label="source" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item name="type" label="type" rules={[{ required: true }]}>
                    <Select
                      showSearch
                      options={relationTypes.map((t) => ({ label: t, value: t }))}
                    />
                  </Form.Item>
                  <Form.Item name="target" label="target" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item name="weight" label="weight">
                    <InputNumber min={0} max={1} step={0.1} />
                  </Form.Item>
                  <Form.Item name="description" label="description">
                    <Input.TextArea autoSize={{ minRows: 3, maxRows: 8 }} />
                  </Form.Item>
                  <Button type="primary" htmlType="submit">
                    创建
                  </Button>
                </Form>
              ),
            },
            {
              key: "update",
              label: "更新",
              children: (
                <Form form={updateForm} layout="vertical" onFinish={submitUpdate}>
                  <Form.Item name="source" label="source" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item name="original_type" label="original_type" rules={[{ required: true }]}>
                    <Select
                      showSearch
                      options={relationTypes.map((t) => ({ label: t, value: t }))}
                    />
                  </Form.Item>
                  <Form.Item name="target" label="target" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item name="new_type" label="new_type（可选，改类型）">
                    <Select
                      allowClear
                      showSearch
                      options={relationTypes.map((t) => ({ label: t, value: t }))}
                    />
                  </Form.Item>
                  <Form.Item name="weight" label="weight">
                    <InputNumber min={0} max={1} step={0.1} />
                  </Form.Item>
                  <Form.Item name="description" label="description">
                    <Input.TextArea autoSize={{ minRows: 3, maxRows: 8 }} />
                  </Form.Item>
                  <Button type="primary" htmlType="submit">
                    更新
                  </Button>
                </Form>
              ),
            },
            {
              key: "delete",
              label: "删除",
              children: (
                <Form form={deleteForm} layout="vertical" onFinish={submitDelete}>
                  <Form.Item name="source" label="source" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item name="type" label="type" rules={[{ required: true }]}>
                    <Select
                      showSearch
                      options={relationTypes.map((t) => ({ label: t, value: t }))}
                    />
                  </Form.Item>
                  <Form.Item name="target" label="target" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                  <Button danger type="primary" htmlType="submit">
                    删除
                  </Button>
                </Form>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
}


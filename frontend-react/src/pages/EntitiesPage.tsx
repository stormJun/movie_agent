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
import type { EntityData, EntitySearchFilter, EntityUpdateData } from "../types/management";
import { createEntity, deleteEntity, getEntityTypes, searchEntities, updateEntity } from "../services/management";

export function EntitiesPage() {
  const [entityTypes, setEntityTypes] = useState<string[]>([]);
  const [loadingTypes, setLoadingTypes] = useState(false);

  const [entities, setEntities] = useState<EntityData[]>([]);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);

  const [searchForm] = Form.useForm<EntitySearchFilter>();
  const [createForm] = Form.useForm<EntityData>();
  const [updateForm] = Form.useForm<EntityUpdateData>();
  const [deleteForm] = Form.useForm<{ id: string }>();

  useEffect(() => {
    (async () => {
      setLoadingTypes(true);
      try {
        const types = await getEntityTypes();
        setEntityTypes(types);
      } catch (e) {
        message.error(e instanceof Error ? e.message : "获取实体类型失败");
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
      const resp = await searchEntities(values);
      setEntities(resp);
      setPage(1);
    } catch (e) {
      setSearchError(e instanceof Error ? e.message : "查询失败");
    } finally {
      setLoadingSearch(false);
    }
  }

  const columns: ColumnsType<EntityData> = useMemo(
    () => [
      { title: "id", dataIndex: "id", width: 260, ellipsis: true },
      { title: "type", dataIndex: "type", width: 180, ellipsis: true },
      { title: "description", dataIndex: "description", ellipsis: true },
    ],
    [],
  );

  async function submitCreate() {
    const values = (await createForm.validateFields()) as EntityData;
    const resp = await createEntity(values);
    if (!resp.success) {
      message.error(resp.message || "创建失败");
      return;
    }
    message.success("创建成功");
    await doSearch();
  }

  async function submitUpdate() {
    const values = (await updateForm.validateFields()) as EntityUpdateData;
    const resp = await updateEntity(values);
    if (!resp.success) {
      message.error(resp.message || "更新失败");
      return;
    }
    message.success("更新成功");
    await doSearch();
  }

  async function submitDelete() {
    const values = (await deleteForm.validateFields()) as { id: string };
    const resp = await deleteEntity(values.id);
    if (!resp.success) {
      message.error(resp.message || "删除失败");
      return;
    }
    message.success("删除成功");
    await doSearch();
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card title="实体管理（CRUD）">
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
                    initialValues={{ term: "", type: undefined, limit: 100 }}
                    onFinish={doSearch}
                  >
                    <Form.Item name="term" label="term">
                      <Input placeholder="id contains ..." allowClear style={{ width: 260 }} />
                    </Form.Item>
                    <Form.Item name="type" label="type">
                      <Select
                        allowClear
                        loading={loadingTypes}
                        style={{ width: 220 }}
                        options={entityTypes.map((t) => ({ label: t, value: t }))}
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
                    rowKey={(row) => row.id}
                    dataSource={entities}
                    loading={loadingSearch}
                    columns={columns}
                    pagination={{
                      current: page,
                      pageSize,
                      showSizeChanger: true,
                      pageSizeOptions: [10, 20, 50, 100, 200],
                      showTotal: (total) => `共 ${total} 条`,
                      onChange: (nextPage, nextPageSize) => {
                        setPageSize(nextPageSize);
                        setPage(nextPageSize !== pageSize ? 1 : nextPage);
                      },
                    }}
                    onRow={(row) => ({
                      onClick: () => {
                        updateForm.setFieldsValue({
                          id: row.id,
                          name: row.name,
                          type: row.type,
                          description: row.description,
                        });
                        deleteForm.setFieldsValue({ id: row.id });
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
                  initialValues={{ id: "", name: "", type: "", description: "" }}
                  onFinish={submitCreate}
                >
                  <Form.Item name="id" label="id" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item name="name" label="name" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item name="type" label="type" rules={[{ required: true }]}>
                    <Select
                      showSearch
                      options={entityTypes.map((t) => ({ label: t, value: t }))}
                    />
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
                  <Form.Item name="id" label="id" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item name="name" label="name">
                    <Input />
                  </Form.Item>
                  <Form.Item name="type" label="type">
                    <Select
                      allowClear
                      showSearch
                      options={entityTypes.map((t) => ({ label: t, value: t }))}
                    />
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
                  <Form.Item name="id" label="id" rules={[{ required: true }]}>
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

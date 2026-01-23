import { useEffect, useState } from "react";
import { Button, List, Typography, Space, theme } from "antd";
import { PlusOutlined, MessageOutlined } from "@ant-design/icons";
import { listConversations, type ConversationItem } from "../services/chat";

interface SessionListProps {
    userId: string;
    currentSessionId: string;
    onSelectSession: (sessionId: string) => void;
    onNewSession: () => void;
    className?: string;
    style?: React.CSSProperties;
}

export function SessionList({
    userId,
    currentSessionId,
    onSelectSession,
    onNewSession,
    className,
    style,
}: SessionListProps) {
    const [sessions, setSessions] = useState<ConversationItem[]>([]);
    const [loading, setLoading] = useState(false);
    const { token } = theme.useToken();

    const fetchSessions = async () => {
        if (!userId) return;
        setLoading(true);
        try {
            const data = await listConversations(userId);
            setSessions(data);
        } catch (e) {
            console.error("Failed to fetch sessions", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSessions();
    }, [userId]);

    // Expose a way to refresh list? 
    // For now simple polling or dependency on currentSessionId might be enough if we want to auto-refresh 
    // when a new session is actually created/interacted with. 
    // Let's trigger refresh when currentSessionId changes, purely to ensure list is up to date 
    // if we just created a new one and sent a message.
    useEffect(() => {
        fetchSessions();
    }, [currentSessionId]);

    return (
        <div
            className={`session-list-container ${className || ""}`}
            style={style}
        >
            <div className="session-list-header">
                <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={onNewSession}
                    block
                    className="new-session-button"
                >
                    新会话
                </Button>
            </div>
            <div className="session-list-content">
                <List
                    loading={loading}
                    dataSource={sessions}
                    renderItem={(item) => {
                        const isSelected = item.session_id === currentSessionId;
                        return (
                            <List.Item
                                onClick={() => onSelectSession(item.session_id)}
                                className={`session-item ${isSelected ? "active" : ""}`}
                            >
                                <div className="session-item-content">
                                    <div className="session-item-header">
                                        <Typography.Text
                                            strong={isSelected}
                                            ellipsis
                                            className="session-date"
                                        >
                                            {new Date(item.updated_at).toLocaleDateString()}
                                        </Typography.Text>
                                        <Typography.Text type="secondary" className="session-time">
                                            {new Date(item.updated_at).toLocaleTimeString([], {
                                                hour: "2-digit",
                                                minute: "2-digit",
                                            })}
                                        </Typography.Text>
                                    </div>
                                    <div className="session-item-body">
                                        <MessageOutlined className="session-icon" />
                                        <Typography.Text
                                            ellipsis
                                            type={isSelected ? undefined : "secondary"}
                                            className="session-title"
                                        >
                                            {item.first_message || "新会话"}
                                        </Typography.Text>
                                    </div>
                                </div>
                            </List.Item>
                        );
                    }}
                />
            </div>
        </div>
    );
}

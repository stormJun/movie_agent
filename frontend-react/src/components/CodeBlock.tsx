import React, { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { CopyOutlined, CheckOutlined } from '@ant-design/icons';

interface CodeBlockProps {
    inline?: boolean;
    className?: string;
    children?: React.ReactNode;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ inline, className, children }) => {
    const [copied, setCopied] = useState(false);
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';

    const handleCopy = () => {
        const text = String(children).replace(/\n$/, '');
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    if (inline) {
        return (
            <code className={className} style={{ backgroundColor: '#f0f0f0', padding: '2px 4px', borderRadius: '4px' }}>
                {children}
            </code>
        );
    }

    return (
        <div className="code-block-wrapper">
            <div className="code-block-header">
                <span className="code-language">{language || 'text'}</span>
                <button className="copy-button" onClick={handleCopy}>
                    {copied ? <CheckOutlined /> : <CopyOutlined />}
                    <span className="copy-text">{copied ? 'Copied!' : 'Copy'}</span>
                </button>
            </div>
            <SyntaxHighlighter
                children={String(children).replace(/\n$/, '')}
                style={vscDarkPlus as any}
                language={language}
                PreTag="div"
                customStyle={{
                    margin: 0,
                    borderBottomLeftRadius: '8px',
                    borderBottomRightRadius: '8px',
                    fontSize: '14px',
                    lineHeight: '1.5',
                }}
            />
        </div>
    );
};

export default CodeBlock;

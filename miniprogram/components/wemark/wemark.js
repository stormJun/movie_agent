const parser = require('./parser');
const richtext = require('./richtext');

/**
 * 将markdown文本中只有一个连续的换行符替换成两个换行符
 * 这样可以确保在markdown渲染时产生正确的段落分隔效果
 * @param markdownText 原始markdown文本
 * @returns 处理后的markdown文本
 */
export function replaceSingleNewlineWithDouble(markdownText) {
    // 使用正则表达式匹配单个换行符（不是连续的多个换行符）
    // (?<!\n) 表示前面不是换行符
    // \n 表示匹配一个换行符
    // (?!\n) 表示后面不是换行符
    return markdownText.replace(/(?<!\n)\n(?!\n)/g, '\n\n');
}

Component({
    options: {
        styleIsolation: 'apply-shared'
    },
    externalClasses: ['external-class'], // 外部类名
    properties: {
        md: {
            type: String,
            value: '',
            observer() {
                this.parseMd();
            }
        },
        type: {
            type: String,
            value: 'wemark'
        },
        link: {
            type: Boolean,
            value: false
        },
        highlight: {
            type: Boolean,
            value: false
        },
        /**
         * 是否支持文本选择
         * @type {Boolean}
         * @default true
         */
        selectable: {
            type: Boolean,
            value: true
        }
    },
    data: {
        parsedData: {},
        richTextNodes: [],
        hasTable: false
    },
    methods: {
        parseMd() {
            if (this.data.md) {
                const md = replaceSingleNewlineWithDouble(this.data.md);
                var parsedData = parser.parse(md, {
                    link: this.data.link,
                    highlight: this.data.highlight
                });

                // 检查是否存在表格
                let hasTable = false;
                let tableData = [];

                // 处理数据，分离表格和非表格内容
                const processedData = [];

                for (let i = 0; i < parsedData.length; i++) {
                    const node = parsedData[i];
                    if (node.type === 'table_tr') {
                        hasTable = true;

                        // 收集完整的表格数据
                        const tableNodes = [];
                        let tmpNode = node;
                        while (tmpNode && tmpNode.type === 'table_tr') {
                            tableNodes.push(tmpNode);
                            i++;
                            tmpNode = i < parsedData.length ? parsedData[i] : null;
                        }

                        // 将指针回退一位，因为外层循环会再加一
                        i--;

                        // 保存表格数据以便使用rich-text渲染
                        tableData.push({
                            type: 'table',
                            content: tableNodes
                        });

                        // 在原数据中放置一个标记，表示这里需要渲染表格
                        processedData.push({
                            type: 'table_marker',
                            tableIndex: tableData.length - 1
                        });
                    } else {
                        processedData.push(node);
                    }
                }

                // 生成表格的rich-text节点
                const tableRichTextNodes = [];
                if (hasTable) {
                    tableData.forEach(table => {
                        // 使用getTableNode函数直接处理完整的表格数据
                        const tableRichTextNode = richtext.getTableNode(table.content);
                        tableRichTextNodes.push(tableRichTextNode);
                    });
                }

                // 如果使用rich-text模式，则生成所有内容的富文本节点
                if (this.data.type === 'rich-text') {
                    const richTextNodes = richtext.getRichTextNodes(parsedData);
                    this.setData({
                        richTextNodes
                    });
                }

                this.setData({
                    parsedData: processedData,
                    hasTable: hasTable,
                    tableRichTextNodes: tableRichTextNodes
                });
            }
        }
    }
});

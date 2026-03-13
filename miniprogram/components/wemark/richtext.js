exports.getRichTextNodes = function(parsedData) {
    var richTextNodes = [];

    var getNodeName = (function() {
        return function(type, nodeType = 'inline') {
            if (type === 'table_tr') {
                return 'tr';
            } else {
                // 有多级的，block返回第一级，inline返回最后一级
                if (type.indexOf('_') > -1) {
                    var typePart = type.split('_');
                    if (nodeType === 'inline') {
                        return typePart.pop();
                    } else {
                        return typePart[0];
                    }
                }
            }
            return type;
        };
    })();

    var getBlockNode = function(node) {
        var nodeType = node.type;
        // console.log('nodeType:', nodeType);
        var richTextNode = {
            name: getNodeName(nodeType, 'inline'),
            attrs: {
                class: 'wemark_block_' + nodeType
            },
            children: []
        };
        if (node.isArray) {
            node.content.forEach((childNode) => {
                if (['text', 'code', 'strong', 'deleted', 'em'].indexOf(childNode.type) > -1) {
                    richTextNode.children.push({
                        name: 'span',
                        attrs: {
                            class: 'wemark_inline_' + childNode.type
                        },
                        children: [{
                            type: 'text',
                            text: childNode.content
                        }]
                    });
                } else if (node.highlight) {
                    if (typeof childNode === 'string') {
                        richTextNode.children.push({
                            name: 'span',
                            attrs: {
                                class: 'wemark_inline_code_text'
                            },
                            children: [{
                                type: 'text',
                                text: childNode
                            }]
                        });
                    } else {
                        richTextNode.children.push({
                            name: 'span',
                            attrs: {
                                class: 'wemark_inline_code_' + childNode.type
                            },
                            children: [{
                                type: 'text',
                                text: childNode.content
                            }]
                        });
                    }
                } else if (childNode.type === 'link') {
                    richTextNode.children.push({
                        name: 'a',
                        attrs: {
                            class: 'wemark_inline_link',
                            href: childNode.data.href
                        },
                        children: [{
                            type: 'text',
                            text: childNode.content
                        }]
                    });
                } else if (childNode.type === 'image') {
                    richTextNode.children.push({
                        name: 'img',
                        attrs: {
                            mode: 'widthFix',
                            class: 'wemark_inline_image',
                            src: childNode.src
                        }
                    });
                } else if (childNode.type === 'table_th') {
                    richTextNode.children.push({
                        name: 'th',
                        attrs: {
                            class: 'wemark_inline_table_th'
                        },
                        children: [{
                            type: 'text',
                            text: childNode.content
                        }]
                    });
                } else if (childNode.type === 'table_td') {
                    richTextNode.children.push({
                        name: 'td',
                        attrs: {
                            class: 'wemark_inline_table_td'
                        },
                        children: [{
                            type: 'text',
                            text: childNode.content
                        }]
                    });
                }
            });
        } else if (node.type === 'code') {
            richTextNode.children = [{
                name: 'code',
                children: [{
                    type: 'text',
                    text: node.content
                }]
            }];
        }
        return richTextNode;
    };

    // 特殊处理表格结构
    var getTableNode = function(tableRows) {
        var tableNode = {
            name: 'table',
            attrs: {
                class: 'wemark_block_table',
                style: 'width:auto; min-width:100%; table-layout:auto; border-collapse:collapse;'
            },
            children: []
        };

        // 添加表头行（如果存在）
        if (tableRows.length > 0) {
            var headerRow = tableRows[0];
            var headerTrNode = {
                name: 'tr',
                attrs: {
                    class: 'wemark_block_table_tr'
                },
                children: []
            };

            headerRow.content.forEach(function(cell) {
                if (cell.type === 'table_th') {
                    headerTrNode.children.push({
                        name: 'th',
                        attrs: {
                            class: 'wemark_inline_table_th',
                            style: 'white-space:nowrap; min-width:120rpx; max-width:350rpx; padding:8px 10px;'
                        },
                        children: [{
                            type: 'text',
                            text: cell.content
                        }]
                    });
                }
            });

            tableNode.children.push(headerTrNode);
        }

        // 添加表格数据行
        for (var rowIndex = 1; rowIndex < tableRows.length; rowIndex++) {
            var dataRow = tableRows[rowIndex];
            var dataTrNode = {
                name: 'tr',
                attrs: {
                    class: 'wemark_block_table_tr'
                },
                children: []
            };

            dataRow.content.forEach(function(cell) {
                if (cell.type === 'table_td') {
                    dataTrNode.children.push({
                        name: 'td',
                        attrs: {
                            class: 'wemark_inline_table_td',
                            style: 'white-space: normal; min-width:120rpx; max-width:350rpx; padding:8px 10px;'
                        },
                        children: [{
                            type: 'text',
                            text: cell.content
                        }]
                    });
                }
            });

            tableNode.children.push(dataTrNode);
        }

        return tableNode;
    };

    for (var i = 0; i < parsedData.length; i++) {
        var node = parsedData[i];
        if (node.type === 'table_tr') {
            var tableRows = [];
            var tmpNode = node;

            // 收集所有表格行
            while (tmpNode && tmpNode.type === 'table_tr') {
                tableRows.push(tmpNode);
                tmpNode = parsedData[++i];
            }

            // 调整索引，因为循环会再次增加
            i--;

            // 使用优化的表格节点构建函数
            richTextNodes.push(getTableNode(tableRows));
        } else {
            richTextNodes.push(getBlockNode(node));
        }
    }

    return richTextNodes;
};

// 导出getTableNode函数，使其可以在wemark.js中直接使用
exports.getTableNode = function(tableRows) {
    var tableNode = {
        name: 'table',
        attrs: {
            class: 'wemark_block_table',
            style: 'width:auto; min-width:100%; table-layout:auto; border-collapse:collapse;'
        },
        children: []
    };

    // 添加表头行（如果存在）
    if (tableRows.length > 0) {
        var headerRow = tableRows[0];
        var headerTrNode = {
            name: 'tr',
            attrs: {
                class: 'wemark_block_table_tr'
            },
            children: []
        };

        headerRow.content.forEach(function(cell) {
            if (cell.type === 'table_th') {
                headerTrNode.children.push({
                    name: 'th',
                    attrs: {
                        class: 'wemark_inline_table_th',
                        style: 'white-space:nowrap; min-width:120rpx; max-width:350rpx; padding:8px 10px;'
                    },
                    children: [{
                        type: 'text',
                        text: cell.content
                    }]
                });
            }
        });

        tableNode.children.push(headerTrNode);
    }

    // 添加表格数据行
    for (var rowIndex = 1; rowIndex < tableRows.length; rowIndex++) {
        var dataRow = tableRows[rowIndex];
        var dataTrNode = {
            name: 'tr',
            attrs: {
                class: 'wemark_block_table_tr'
            },
            children: []
        };

        dataRow.content.forEach(function(cell) {
            if (cell.type === 'table_td') {
                dataTrNode.children.push({
                    name: 'td',
                    attrs: {
                        class: 'wemark_inline_table_td',
                        style: 'white-space:normal; min-width:120rpx; max-width:350rpx; padding:8px 10px;'
                    },
                    children: [{
                        type: 'text',
                        text: cell.content
                    }]
                });
            }
        });

        tableNode.children.push(dataTrNode);
    }

    return tableNode;
};

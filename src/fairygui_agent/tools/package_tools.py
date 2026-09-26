"""包/资源查询工具 - 从 FairyGUI-MCP 移植

移植说明：
- 原版使用 fastmcp，改为第 1 名的 mcp.server.fastmcp
- 原版通过文件轮询与编辑器通信，改为使用第 1 名的 bridge_client
- 保留所有工具函数，适配第 1 名的命名规范（fgui_ 前缀）
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP
import xml.etree.ElementTree as ET


def register(mcp: FastMCP, bridge_client) -> None:
    """注册包查询工具"""

    @mcp.tool()
    def fgui_search_component(name_pattern: str) -> str:
        """在所有包中搜索组件

        Args:
            name_pattern: 组件名称模式（支持部分匹配）

        Returns:
            匹配的组件列表
        """
        status = bridge_client.describe_status()
        project_path = status.get("project_path")
        if not project_path:
            return "错误：未选择 FairyGUI 工程，请先调用 fgui_use_project"

        packages_dir = Path(project_path) / "assets"
        if not packages_dir.exists():
            return f"错误：UI 项目目录不存在: {packages_dir}"

        results = []
        for pkg_dir in packages_dir.iterdir():
            if not pkg_dir.is_dir():
                continue

            package_xml = pkg_dir / "package.xml"
            if not package_xml.exists():
                continue

            try:
                tree = ET.parse(package_xml)
                root = tree.getroot()
                pkg_name = pkg_dir.name

                resources = root.find("resources")
                if not resources:
                    continue

                for res in resources:
                    if res.tag == "component":
                        res_name = res.get("name", "")
                        if name_pattern.lower() in res_name.lower():
                            results.append({
                                "package": pkg_name,
                                "name": res_name,
                                "id": res.get("id", ""),
                                "path": res.get("path", "/"),
                                "exported": res.get("exported", "false") == "true"
                            })
            except Exception:
                continue

        if not results:
            return f"未找到匹配 '{name_pattern}' 的组件"

        lines = [f"找到 {len(results)} 个匹配的组件:\n"]
        for r in results:
            export_mark = " [导出]" if r["exported"] else ""
            lines.append(f"  • {r['package']}/{r['name']}{export_mark}")
            lines.append(f"    ID: {r['id']}")

        return "\n".join(lines)

    @mcp.tool()
    def fgui_get_package_info(package_name: str) -> str:
        """获取指定 UI 包的详细信息

        Args:
            package_name: 包名称

        Returns:
            包的详细信息，包括所有资源列表
        """
        status = bridge_client.describe_status()
        project_path = status.get("project_path")
        if not project_path:
            return "错误：未选择 FairyGUI 工程，请先调用 fgui_use_project"

        pkg_dir = Path(project_path) / "assets" / package_name
        package_xml = pkg_dir / "package.xml"

        if not pkg_dir.exists():
            return f"错误：包不存在: {package_name}"

        if not package_xml.exists():
            return f"错误：package.xml 不存在: {package_xml}"

        try:
            tree = ET.parse(package_xml)
            root = tree.getroot()

            pkg_id = root.get("id", "")

            # 解析资源
            resources = root.find("resources")
            items = {
                "components": [],
                "images": [],
                "fonts": [],
                "folders": [],
                "others": []
            }

            if resources:
                for res in resources:
                    res_type = res.tag
                    res_id = res.get("id", "")
                    res_name = res.get("name", "")
                    exported = res.get("exported", "false") == "true"

                    item_info = f"{res_name} (ID: {res_id}, 导出: {exported})"

                    if res_type == "component":
                        items["components"].append(item_info)
                    elif res_type == "image":
                        items["images"].append(item_info)
                    elif res_type == "font":
                        items["fonts"].append(item_info)
                    elif res_type == "folder":
                        items["folders"].append(item_info)
                    else:
                        items["others"].append(f"{res_type}: {item_info}")

            # 格式化输出
            lines = [
                f"# 包信息: {pkg_name}",
                "",
                f"- **ID**: {pkg_id}",
                f"- **路径**: {pkg_dir.relative_to(project_path)}",
                "",
                "## 资源统计",
                "",
                "| 类型 | 数量 |",
                "|------|------|",
                f"| 组件 | {len(items['components'])} |",
                f"| 图片 | {len(items['images'])} |",
                f"| 字体 | {len(items['fonts'])} |",
                f"| 文件夹 | {len(items['folders'])} |",
            ]

            if items["components"]:
                lines.append("\n## 组件列表\n")
                for comp in items["components"][:20]:
                    lines.append(f"- {comp}")
                if len(items["components"]) > 20:
                    lines.append(f"- ... 还有 {len(items['components']) - 20} 个组件")

            return "\n".join(lines)

        except Exception as e:
            return f"解析错误: {str(e)}"

    @mcp.tool()
    def fgui_list_resources(
        package_name: str,
        resource_type: Optional[str] = None
    ) -> str:
        """列出包内的资源

        Args:
            package_name: 包名称
            resource_type: 资源类型过滤 (component/image/font/folder)，不指定则列出全部

        Returns:
            资源列表
        """
        status = bridge_client.describe_status()
        project_path = status.get("project_path")
        if not project_path:
            return "错误：未选择 FairyGUI 工程，请先调用 fgui_use_project"

        pkg_dir = Path(project_path) / "assets" / package_name
        package_xml = pkg_dir / "package.xml"

        if not pkg_dir.exists():
            return f"错误：包不存在: {package_name}"

        try:
            tree = ET.parse(package_xml)
            root = tree.getroot()

            resources = root.find("resources")
            if not resources:
                return "包内没有资源"

            items = []

            for res in resources:
                res_type = res.tag
                res_id = res.get("id", "")
                res_name = res.get("name", "")
                res_path = res.get("path", "/")
                exported = res.get("exported", "false") == "true"

                # 类型过滤
                if resource_type and res_type != resource_type:
                    continue

                items.append({
                    "type": res_type,
                    "id": res_id,
                    "name": res_name,
                    "path": res_path,
                    "exported": exported
                })

            if not items:
                if resource_type:
                    return f"包内没有类型为 '{resource_type}' 的资源"
                else:
                    return "包内没有资源"

            # 格式化输出
            lines = [f"包 '{package_name}' 内的资源 ({len(items)} 个):\n"]

            for item in items:
                export_mark = " [导出]" if item["exported"] else ""
                lines.append(f"  [{item['type']}] {item['name']}{export_mark}")
                lines.append(f"    ID: {item['id']}, 路径: {item['path']}")

            return "\n".join(lines)

        except Exception as e:
            return f"解析错误: {str(e)}"
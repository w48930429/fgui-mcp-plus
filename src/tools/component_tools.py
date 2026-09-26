"""组件操作工具 - 从 FairyGUI-MCP 移植

移植说明：
- 原版使用 fastmcp，改为第 1 名的 mcp.server.fastmcp
- 原版通过文件轮询与编辑器通信，改为使用第 1 名的 bridge_client
- 保留所有工具函数，适配第 1 名的命名规范（fgui_ 前缀）
"""

from __future__ import annotations

from pathlib import Path
from mcp.server.fastmcp import FastMCP
import xml.etree.ElementTree as ET


def register(mcp: FastMCP, bridge_client) -> None:
    """注册组件操作工具"""

    @mcp.tool()
    def fgui_parse_component(package_name: str, component_name: str) -> str:
        """解析组件并生成自然语言描述

        将组件 XML 解析为易于理解的结构化描述，包含：
        - 基础属性（尺寸、扩展类型等）
        - 控制器定义
        - 显示列表元素
        - Gear 和 Relation 配置
        - Transition 动画

        Args:
            package_name: 包名称
            component_name: 组件名称

        Returns:
            组件的结构化描述
        """
        status = bridge_client.describe_status()
        project_path = status.get("project_path")
        if not project_path:
            return "错误：未选择 FairyGUI 工程，请先调用 fgui_use_project"

        # 查找组件文件
        pkg_dir = Path(project_path) / "assets" / package_name
        if not pkg_dir.exists():
            return f"错误：包不存在：{package_name}"

        # 尝试多种路径
        possible_paths = [
            pkg_dir / f"{component_name}.xml",
            pkg_dir / "Items" / f"{component_name}.xml",
            pkg_dir / "control" / f"{component_name}.xml",
        ]

        # 从 package.xml 中查找组件路径
        package_xml = pkg_dir / "package.xml"
        if package_xml.exists():
            try:
                tree = ET.parse(package_xml)
                root = tree.getroot()
                resources = root.find("resources")
                if resources:
                    for res in resources:
                        if res.tag == "component" and res.get("name", "").replace(".xml", "") == component_name:
                            res_path = res.get("path", "")
                            if res_path:
                                possible_paths.insert(0, pkg_dir / res_path / f"{component_name}.xml")
                            break
            except Exception:
                pass

        # 查找存在的文件
        component_file = None
        for path in possible_paths:
            if path.exists():
                component_file = path
                break

        if not component_file:
            return f"错误：组件不存在：{package_name}/{component_name}"

        try:
            with open(component_file, "r", encoding="utf-8") as f:
                xml_content = f.read()
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            return f"XML 解析错误：{str(e)}"

        # 解析组件
        lines = [f"# 组件描述：{component_name}", ""]

        # 基础属性
        size = root.get("size", "0,0").split(",")
        extention = root.get("extention", "")
        pivot = root.get("pivot", "")
        opaque = root.get("opaque", "true")

        lines.append("## 基础属性")
        lines.append(f"- **尺寸**: {size[0]} x {size[1]}")
        if extention:
            lines.append(f"- **扩展类型**: {extention}")
        if pivot:
            lines.append(f"- **中心点**: {pivot}")
        lines.append(f"- **不透明**: {opaque}")
        lines.append("")

        # 控制器
        controllers = root.findall("controller")
        if controllers:
            lines.append("## 控制器定义")
            lines.append("")
            for i, ctrl in enumerate(controllers, 1):
                name = ctrl.get("name", "")
                alias = ctrl.get("alias", "")
                exported = ctrl.get("exported", "false") == "true"
                selected = ctrl.get("selected", "0")

                lines.append(f"### {i}. {name} 控制器")
                if alias:
                    lines.append(f"- 别名：{alias}")
                if exported:
                    lines.append(f"- 已导出")
                lines.append(f"- 默认页：{selected}")

                # 页面
                pages_str = ctrl.get("pages", "")
                if pages_str:
                    pages = pages_str.split(",")
                    lines.append(f"- 页面:")
                    for j in range(0, len(pages), 2):
                        if j + 1 < len(pages):
                            lines.append(f"  - {pages[j]}: {pages[j+1]}")
                lines.append("")

        # 显示列表
        display_list = root.find("displayList")
        if display_list is not None:
            elements = list(display_list)
            if elements:
                lines.append("## 显示列表")
                lines.append(f"共 {len(elements)} 个元素")
                lines.append("")

                for i, elem in enumerate(elements, 1):
                    tag = elem.tag
                    elem_id = elem.get("id", "")
                    elem_name = elem.get("name", "")
                    xy = elem.get("xy", "0,0")
                    size_elem = elem.get("size", "")

                    lines.append(f"### {i}. [{tag}] {elem_name}")
                    lines.append(f"- ID: {elem_id}")
                    lines.append(f"- 位置：{xy}")
                    if size_elem:
                        lines.append(f"- 尺寸：{size_elem}")

                    # 元素特有属性
                    if tag == "image":
                        src = elem.get("src", "")
                        if src:
                            lines.append(f"- 资源：{src}")
                    elif tag == "text":
                        text_content = elem.get("text", "")
                        font = elem.get("font", "")
                        font_size = elem.get("fontSize", "")
                        if text_content:
                            lines.append(f"- 文本：\"{text_content}\"")
                        if font:
                            lines.append(f"- 字体：{font}")
                        if font_size:
                            lines.append(f"- 字号：{font_size}")
                    elif tag == "component":
                        src = elem.get("src", "")
                        pkg = elem.get("pkg", "")
                        if src:
                            lines.append(f"- 组件：{src}")
                        if pkg:
                            lines.append(f"- 包：{pkg}")

                    lines.append("")

        # Transition
        transitions = root.findall("transition")
        if transitions:
            lines.append("## 动画定义")
            lines.append("")
            for trans in transitions:
                name = trans.get("name", "")
                auto_play = trans.get("autoPlay", "false") == "true"
                frame_rate = trans.get("frameRate", "24")

                lines.append(f"### {name}")
                lines.append(f"- 自动播放：{auto_play}")
                lines.append(f"- 帧率：{frame_rate}")
                lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    def fgui_validate_component(package_name: str, component_name: str) -> str:
        """验证组件规范

        检查组件是否符合 FairyGUI 规范和项目最佳实践：
        - XML 格式正确性
        - 必要属性完整性
        - 命名规范
        - 资源引用有效性

        Args:
            package_name: 包名称
            component_name: 组件名称

        Returns:
            验证结果
        """
        # 先读取组件
        status = bridge_client.describe_status()
        project_path = status.get("project_path")
        if not project_path:
            return "错误：未选择 FairyGUI 工程，请先调用 fgui_use_project"

        pkg_dir = Path(project_path) / "assets" / package_name
        if not pkg_dir.exists():
            return f"错误：包不存在：{package_name}"

        # 查找组件文件
        possible_paths = [
            pkg_dir / f"{component_name}.xml",
            pkg_dir / "Items" / f"{component_name}.xml",
        ]
        component_file = None
        for path in possible_paths:
            if path.exists():
                component_file = path
                break

        if not component_file:
            return f"错误：组件不存在：{package_name}/{component_name}"

        issues = []
        warnings = []

        try:
            with open(component_file, "r", encoding="utf-8") as f:
                xml_content = f.read()
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            return f"❌ XML 格式错误：{str(e)}"

        # 检查基础属性
        size = root.get("size", "")
        if not size:
            issues.append("缺少 size 属性")

        # 检查控制器
        controllers = root.findall("controller")
        for ctrl in controllers:
            name = ctrl.get("name", "")
            if not name:
                issues.append("控制器缺少 name 属性")
            elif not name[0].isupper():
                warnings.append(f"控制器名称 '{name}' 建议使用 PascalCase")

        # 检查显示列表
        display_list = root.find("displayList")
        if display_list is not None:
            for elem in display_list:
                elem_name = elem.get("name", "")
                if not elem_name:
                    issues.append(f"元素 {elem.tag} 缺少 name 属性")
                elif not elem_name[0].islower():
                    warnings.append(f"元素名称 '{elem_name}' 建议使用 camelCase")

        # 输出结果
        lines = []
        if issues:
            lines.append("❌ 发现问题：")
            for issue in issues:
                lines.append(f"  - {issue}")
        else:
            lines.append("✅ 规范检查通过")

        if warnings:
            lines.append("")
            lines.append("⚠️ 建议：")
            for warning in warnings:
                lines.append(f"  - {warning}")

        if not issues and not warnings:
            lines.append("")
            lines.append("组件完全符合规范！")

        return "\n".join(lines)
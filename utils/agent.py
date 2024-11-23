def parse_text(rsp):
    pattern = r"```text(.*)```"
    match = re.search(pattern, rsp, re.DOTALL)
    text = match.group(1) if match else rsp
    return text


# 总体情节的构建师角色
class StoryPlanner(Action):
    PROMPT_TEMPLATE: str = """
    根据以下主题或背景设定，创建一份中篇小说的总体情节架构:
    主题:{theme}:
    要求:
    - 精心构建核心情节，确保主线清晰且引人入胜
    - 定义主要人物及其复杂的关系，注意人物的动机和转变
    - 描述主要冲突及其发展，包括内外部冲突，并提供情节发展方向
    - 设计具有张力和深度的转折点与高潮，确保情节充满悬念和吸引力
    - 不需要详细的小说叙述，仅提供一个具体且完整的整体架构，包括情节走向和人物发展
    输出格式:```text yourtext```
    """

    name: str = "StoryPlanner"

    async def run(self, theme: str):
        prompt = self.PROMPT_TEMPLATE.format(theme=theme)
        rsp = await self._aask(prompt)
        text = parse_text(rsp)
        open('workspace/novelSet.txt', 'w').write(text)
        return text
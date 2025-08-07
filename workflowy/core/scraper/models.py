"""
Data models for Workflowy scraping
"""

class AuxiliaryProject:
    def __init__(self, shareId: str):
        self.shareId = shareId

class ProjectTreeData:
    def __init__(self, auxiliaryProjectTreeInfos: list):
        self.auxiliaryProjectTreeInfos = [
            AuxiliaryProject(info.get('shareId', '')) if isinstance(info, dict) else 
            AuxiliaryProject(info.shareId) if hasattr(info, 'shareId') else
            info 
            for info in auxiliaryProjectTreeInfos
        ]

class InitializationData:
    def __init__(self, projectTreeData: dict):
        self.projectTreeData = ProjectTreeData(
            projectTreeData.get('auxiliaryProjectTreeInfos', [])
        )

    def transform(self) -> list[str]:
        return [info.shareId for info in self.projectTreeData.auxiliaryProjectTreeInfos]

class WorkflowyNode:
    def __init__(self, node_id: str, node_name: str, content: str, timestamp: float = None):
        self.node_id = node_id
        self.node_name = node_name
        self.content = content
        self.timestamp = timestamp

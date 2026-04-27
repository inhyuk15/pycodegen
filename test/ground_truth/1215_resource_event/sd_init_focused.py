class FileStorageObserver(RunObserver):
    def find_or_save(self, filename, store_dir: Path):
        ...
    def initialize(
        self,
        basedir,
        resource_dir,
        source_dir,
        template,
        priority=DEFAULT_FILE_STORAGE_PRIORITY,
        copy_artifacts=True,
        copy_sources=True,
    ):
        self.basedir = str(basedir)
        self.resource_dir = resource_dir
        self.source_dir = source_dir
        self.template = template
        self.priority = priority
        self.copy_artifacts = copy_artifacts
        self.copy_sources = copy_sources
        self.dir = None
        self.run_entry = None
        self.config = None
        self.info = None
        self.cout = ""
        self.cout_write_cursor = 0
    def save_json(self, obj, filename):
        ...

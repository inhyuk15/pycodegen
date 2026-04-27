class FileStorageObserver(RunObserver):
    def find_or_save(self, filename, store_dir: Path):
        try:
            Path(filename).resolve().relative_to(Path(self.basedir).resolve())
            is_relative_to = True
        except ValueError:
            is_relative_to = False

        if is_relative_to and not self.copy_artifacts:
            return filename
        else:
            store_dir.mkdir(parents=True, exist_ok=True)
            source_name, ext = os.path.splitext(os.path.basename(filename))
            md5sum = get_digest(filename)
            store_name = source_name + "_" + md5sum + ext
            store_path = store_dir / store_name
            if not store_path.exists():
                copyfile(filename, str(store_path))
            return store_path
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
        with open(os.path.join(self.dir, filename), "w") as f:
            json.dump(flatten(obj), f, sort_keys=True, indent=2)
            f.flush()

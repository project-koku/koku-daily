help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo ""
	@echo "--- General Commands ---"
	@echo "  help                                  show this message"
	@echo "  lint                                  run pre-commit against the project"
	@echo ""

lint:
	pre-commit run --all-files

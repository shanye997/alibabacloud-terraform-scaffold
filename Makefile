# Makefile for building deployment packages

# Color output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

.PHONY: help replace-placeholders prepare-package build-package

help:
	@echo "Usage: make <target> PROFILE=<profile>"
	@echo ""
	@echo "Available targets:"
	@echo "  replace-placeholders  - Replace placeholders in tfdeploy.yaml files"
	@echo "  prepare-package       - Prepare deployment package (replace placeholders)"
	@echo "  build-package         - Build deployment package structure"
	@echo ""
	@echo "Examples:"
	@echo "  make replace-placeholders PROFILE=dev"
	@echo "  make prepare-package PROFILE=prod"
	@echo "  make build-package PROFILE=staging"

# Validate PROFILE parameter
check-profile:
	@if [ -z "$(PROFILE)" ]; then \
		echo "$(RED)Error: PROFILE parameter is required$(NC)"; \
		echo "Usage: make <target> PROFILE=<profile>"; \
		exit 1; \
	fi

# Replace placeholders in {{PROFILE.xxx}} format
replace-placeholders: check-profile
	@PROFILE_FILE="deployments/$(PROFILE)/profile.yaml"; \
	if [ ! -f "$$PROFILE_FILE" ]; then \
		echo "$(YELLOW)Warning: $$PROFILE_FILE not found, skipping placeholder replacement$(NC)"; \
		exit 0; \
	fi; \
	echo "$(GREEN)Replacing placeholders for profile: $(PROFILE)$(NC)"; \
	YQ_CMD="$(CURDIR)/scripts/yq"; \
	if [ ! -f "$$YQ_CMD" ]; then \
		YQ_CMD="scripts/yq"; \
	fi; \
	for file in $$(find deployments/$(PROFILE) -name "tfdeploy.yaml" -type f ! -path "*/\.*"); do \
		FILE_UPDATED=0; \
		for key in $$($$YQ_CMD 'keys | .[]' $$PROFILE_FILE 2>/dev/null); do \
			if [ -n "$$key" ]; then \
				VALUE=$$($$YQ_CMD ".$$key" $$PROFILE_FILE 2>/dev/null | tr -d '"'); \
				if [ -n "$$VALUE" ]; then \
					PLACEHOLDER="{{PROFILE.$$key}}"; \
					if grep -q "$$PLACEHOLDER" "$$file" 2>/dev/null; then \
						sed -i.bak "s|$$PLACEHOLDER|$$VALUE|g" "$$file" && \
						FILE_UPDATED=1; \
						echo "    Replaced $$PLACEHOLDER with $$VALUE"; \
					fi; \
				fi; \
			fi; \
		done; \
		if [ $$FILE_UPDATED -eq 1 ]; then \
			echo "  Updated: $$file"; \
		fi; \
	done; \
	find code -name "*.bak" -type f -delete 2>/dev/null || true; \
	echo "$(GREEN)Placeholder replacement completed$(NC)"

# Prepare deployment package by replacing placeholders
prepare-package: replace-placeholders
	@echo "$(GREEN)Preparing package for profile: $(PROFILE)$(NC)"
	@if [ -d "deployments/$(PROFILE)" ]; then \
		cp -rp deployments/$(PROFILE)/* stacks/ 2>/dev/null || echo "$(YELLOW)No files to copy or directory does not exist$(NC)"; \
	fi; \
	rm -rf deployments/; \
	echo "$(GREEN)Package structure prepared: $(PROFILE)$(NC)"

# Build deployment package and calculate hash
build-package: prepare-package
	@echo "$(GREEN)Building package for profile: $(PROFILE)$(NC)"
	@ZIP_FILE="code-$(PROFILE).zip"; \
	zip -q -r -X $$ZIP_FILE . -x "*.git*" "*.terraform*" "bootstrap/*" "scripts/*" "*.zip" "*.bak"; \
	if [ ! -f $$ZIP_FILE ]; then \
		echo "$(RED)Error: Failed to create $$ZIP_FILE$(NC)"; \
		exit 1; \
	fi; \
	echo "$(GREEN)Package created: $$ZIP_FILE$(NC)"; \
	bash -c '\
		ZIP_FILE="'"$$ZIP_FILE"'"; \
		extract_crc32() { \
			local zip_file=$$1; \
			zipinfo -v "$$zip_file" | grep -E "^.*32-bit CRC value.*$$" | awk "{print \$$NF}"; \
		}; \
		extract_filenames() { \
			local zip_file=$$1; \
			zipinfo -v "$$zip_file" | grep -E "^.*Central directory entry.*$$" | awk "{print \$$NF}"; \
		}; \
		calculate_zip_hash() { \
			local zip_file=$$1; \
			local crc_values=$$(extract_crc32 "$$zip_file"); \
			local filenames=$$(extract_filenames "$$zip_file"); \
			local combined_data=$$(paste <(echo "$$filenames") <(echo "$$crc_values")); \
			if command -v md5sum >/dev/null 2>&1; then \
				echo "$$combined_data" | md5sum | awk "{print \$$1}"; \
			else \
				echo "$$combined_data" | md5 -q; \
			fi; \
		}; \
		HASH=$$(calculate_zip_hash "$$ZIP_FILE"); \
		echo "Hash: $$HASH" \
	'

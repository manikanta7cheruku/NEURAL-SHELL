"""
main_modules/handlers/base.py
Base class for all Seven action handlers.

Each handler:
  - Declares its tag_name (e.g., "TASK", "SYS")
  - Detects if a brain response contains its tag
  - Extracts parameters from tag
  - Executes the action

Pattern: Command + Strategy
"""

import re


class BaseHandler:
    """
    All Seven handlers inherit from this.
    Provides tag detection and parameter extraction.
    """

    tag_name = None  # override in subclass — e.g. "TASK", "SYS", "WINDOW"

    def can_handle(self, response):
        """
        Check if this response contains our tag.
        Returns True if handler should execute.
        """
        if not self.tag_name or not isinstance(response, str):
            return False
        return f"###{self.tag_name}:" in response

    def extract_params(self, response):
        """
        Extract all instances of this tag from response.
        Returns a list of parameter dicts.

        Example:
          response = "Done. ###TASK: action=create text=foo priority=high"
          returns: [{"action": "create", "text": "foo", "priority": "high"}]
        """
        if not self.tag_name:
            return []

        pattern = rf"###{self.tag_name}:\s*(.*?)(?=###|$)"
        matches = re.findall(pattern, response)

        result = []
        for match in matches:
            params = {}
            for pair in match.strip().split():
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k.strip()] = v.strip()
            if params:
                result.append(params)
        return result

    def execute(self, response, ctx):
        """
        Execute the handler action.
        Must be overridden by subclass.
        """
        raise NotImplementedError(
            f"Handler {self.__class__.__name__} must implement execute()"
        )
import json
import requests
from difflib import SequenceMatcher
from flask import current_app

class MondayDotComInterface:
    """Interface for interacting with Monday.com API"""
    
    def __init__(self, api_token):
        """Initialize the interface with the API token."""
        self.api_token = api_token
        self.api_url = "https://api.monday.com/v2"
        self.headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
            "API-Version": "2023-10"
        }
    
    def execute_query(self, query, variables=None):
        """
        Execute a GraphQL query against the Monday.com API.
        
        Args:
            query: The GraphQL query string
            variables: Optional variables for the query
            
        Returns:
            dict: The API response
        """
        data = {"query": query}
        if variables:
            data["variables"] = variables
            
        return self.send_query_to_monday(data)
    
    def get_item_name_by_id(self, item_id):
        """
        Get the name of an item by its ID.
        
        Args:
            item_id: ID of the item
            
        Returns:
            str: The item name, or None if not found
        """
        query = """
        query ($itemId: ID!) {
            items(ids: [$itemId]) {
                name
            }
        }
        """
        
        variables = {
            "itemId": item_id
        }
        
        result = self.execute_query(query, variables)
        
        if result and "data" in result and "items" in result["data"] and len(result["data"]["items"]) > 0:
            return result["data"]["items"][0]["name"]
        
        return None
    
    def get_item_by_name_on_board(self, board_id, item_name):
        """
        Retrieve detailed information about an item by its name from a specific board.
        
        Args:
            board_id: ID of the board
            item_name: Name of the item to search for
            
        Returns:
            tuple: (item_details, error_message)
        """
        query = """
        query ($boardId: ID!) {
            boards(ids: [$boardId]) {
                items {
                    id
                    name
                    column_values {
                        id
                        text
                        type
                        __typename
                        ... on MirrorValue {
                            display_value
                        }
                    }
                    subitems {
                        id
                        name
                        column_values {
                            id
                            text
                            type
                            __typename
                            ... on MirrorValue {
                                display_value
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "boardId": board_id
        }
        
        result = self.execute_query(query, variables)
        
        if not result or "data" not in result or "boards" not in result["data"] or len(result["data"]["boards"]) == 0:
            return None, "Board not found or API error"
        
        board = result["data"]["boards"][0]
        
        # Find the item with the closest name match
        best_match = None
        best_match_ratio = 0
        
        for item in board["items"]:
            ratio = SequenceMatcher(None, item_name.lower(), item["name"].lower()).ratio()
            if ratio > best_match_ratio and ratio > 0.85:  # Require a high similarity
                best_match_ratio = ratio
                best_match = item
        
        if best_match:
            return best_match, None
        else:
            return None, f"Item '{item_name}' not found on board"
    
    def _build_items_page_query(self, board_id, start_date, cursor=None):
        """
        Build *one* GraphQL query string for the Monday.com `items_page`
        endpoint.  Monday's API rules:
            • FIRST page  → supply **query_params** only  
            • NEXT pages → supply **cursor** only
        Passing both triggers the
        "You must provide either a 'query_params' or a 'cursor', but not both"
        error we are fixing here.
        """
        # ----- build the parameter block -----------------------------------
        params = ["limit: 500"]
        if cursor:
            params.append(f'cursor: "{cursor}"')
        else:
            params.append(f"""
                query_params: {{
                    rules: [{{
                        column_id: "date9__1",
                        compare_value: ["EXACT", "{start_date}"],
                        operator: greater_than_or_equals
                    }}]
                }}""")

        params_block = ",\n".join(params)

        # ----- full GraphQL -------------------------------------------------
        gql = f"""
        query {{
          boards(ids: {board_id}) {{
            items_page(
              {params_block}
            ) {{
              cursor
              items {{
                id
                name
                state
                column_values(ids: ["text3__1", "date9__1"]) {{
                  id
                  text
                  __typename
                  ... on MirrorValue {{
                    display_value
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        # `execute_query` already wraps the string in {"query": …}
        return gql

    def get_tapered_enquiry_projects(self, start_date="2021-01-01"):
        """
        Return active projects whose **Created** date (column `date9__1`)
        is **on or after** `start_date` (YYYY-MM-DD) from the
        "Tapered Enquiry Maintenance" board.
        
        Args:
            start_date: The start date in YYYY-MM-DD format
            
        Returns:
            tuple: (items_list, error_message)
        """
        board_id = "1825117125"
        items = []

        # ---- first page ----------------------------------------------------
        query = self._build_items_page_query(board_id, start_date)
        response = self.execute_query(query)

        if not response:
            return None, "No response from Monday.com"

        if "errors" in response:
            return None, f"Monday.com API error: {response['errors']}"

        try:
            page = response["data"]["boards"][0]["items_page"]
        except (KeyError, IndexError, TypeError):
            return None, "Unexpected payload structure from Monday.com"

        # Collect items & paginate
        def _append_active(page_obj):
            for itm in page_obj.get("items", []):
                if itm.get("state") == "active":
                    items.append(itm)

        _append_active(page)
        cursor = page.get("cursor")

        while cursor:
            query = self._build_items_page_query(board_id, start_date, cursor)
            response = self.execute_query(query)

            # More thorough error checking for nested values
            if not response or "data" not in response:
                break
            
            # Check if boards exists and is not empty
            if not response["data"].get("boards"):
                break
                
            # Access the first board safely
            board = response["data"]["boards"][0] if response["data"]["boards"] else None
            if not board or "items_page" not in board:
                break
                
            page = board["items_page"]
            _append_active(page)
            cursor = page.get("cursor")

        if not items:
            return None, (
                f"No active projects created on or after {start_date} "
                "were found on the Tapered Enquiry Maintenance board."
            )
        return items, ""

    def check_project_exists(self, project_name, similarity_threshold=0.55):
        """
        Check if a project name exists or is similar to any project in the Tapered Enquiry Maintenance board.
        Uses string matching to find similar project names.
        
        Args:
            project_name: The project name to search for
            similarity_threshold: Threshold for string similarity (0.0 to 1.0)
            
        Returns:
            dict: Search results with exists, matches, and error information
        """
        # Initialize result dictionary
        result = {
            'exists': False, 
            'type': 'new',
            'matches': [],
            'best_match': None,
            'similarity_score': 0.0,
            'error': ''
        }
        
        # Get all projects from Monday.com
        projects, error = self.get_tapered_enquiry_projects()
        
        if error:
            result['error'] = error
            return result
        
        if not projects:
            result['error'] = "No projects found to compare against"
            return result
        
        # Find similar projects
        matches = []
        for project in projects:
            project_id = project["id"]
            project_name_value = project["name"]
            
            # Extract the project title from column values
            project_title = project_name_value  # Default to name
            for col in project.get("column_values", []):
                if col.get("id") == "text3__1" and col.get("text"):
                    project_title = col.get("text")
                    break
            
            # Calculate similarity with both name and title
            name_ratio = SequenceMatcher(None, project_name.lower(), project_name_value.lower()).ratio()
            title_ratio = SequenceMatcher(None, project_name.lower(), project_title.lower()).ratio() if project_title else 0
            best_ratio = max(name_ratio, title_ratio)
            
            if best_ratio >= similarity_threshold:
                matches.append({
                    'id': project_id,
                    'name': project_name_value,
                    'title': project_title,
                    'similarity': best_ratio
                })
        
        # Sort matches by similarity score (highest first)
        matches = sorted(matches, key=lambda x: x['similarity'], reverse=True)
        
        # Limit to top 5 matches
        matches = matches[:5]
        
        # Update result dictionary
        result['matches'] = matches
        
        if matches:
            best_match = matches[0]
            result['exists'] = True
            result['type'] = 'existing'
            result['best_match'] = best_match
            result['similarity_score'] = best_match['similarity']
        
        return result
    
    def get_project_by_id(self, project_id):
        """
        Get a project directly by its ID using the items endpoint.
        
        Args:
            project_id: ID of the project in Monday.com
            
        Returns:
            tuple: (project_details, error_message)
        """
        query = """
        query {
            items(ids: [%s]) {
                id
                name
                board {
                    id
                }
                column_values {
                    id
                    text
                    __typename
                    ... on MirrorValue {
                        display_value
                    }
                }
                subitems {
                    id
                    name
                    column_values {
                        id
                        text
                        __typename
                        ... on MirrorValue {
                            display_value
                        }
                    }
                }
            }
        }
        """ % project_id
        
        result = self.execute_query(query)
        
        if result and "data" in result and "items" in result["data"] and len(result["data"]["items"]) > 0:
            return result["data"]["items"][0], None
        
        error_msg = "Project not found"
        if result and "errors" in result:
            error_msg = f"API error: {result['errors']}"
        
        return None, error_msg
    
    def send_query_to_monday(self, query):
        """
        Send a GraphQL query to Monday.com.
        
        Args:
            query: The GraphQL query string or JSON-formatted query object
            
        Returns:
            dict: The API response
        """
        # Ensure the query is properly formatted
        if isinstance(query, str):
            try:
                query_data = json.loads(query)
            except json.JSONDecodeError:
                # If it's not a JSON string, assume it's a GraphQL query string
                query_data = {"query": query}
        else:
            query_data = query
        
        try:
            response = requests.post(
                self.api_url,
                json=query_data,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                # Check for GraphQL errors
                if "errors" in result:
                    print(f"Error: {response.status_code}")
                    print(f"GraphQL Errors: {result['errors']}")
                return result
            else:
                print(f"Error: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"Exception in send_query_to_monday: {e}")
            return None 
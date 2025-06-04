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
        Uses Monday.com's built-in smart word-by-word search for better results.
        
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
        
        board_id = "1825117125"
        start_date = "2021-01-01"
        
        def filter_meaningful_words(text):
            """
            Filter out house numbers, postcodes, and other irrelevant words,
            keeping only meaningful location/building name words.
            """
            import re
            
            words = [word.strip() for word in text.split() if word.strip()]
            filtered_words = []
            
            for word in words:
                # Skip house numbers (pure digits or digits with letters like "100A")
                if re.match(r'^\d+[A-Z]*$', word.upper()):
                    continue
                    
                # Skip postcode patterns (e.g., "SW6", "4LX", "M1", "B23")
                if re.match(r'^[A-Z]{1,2}\d{1,2}[A-Z]?$', word.upper()):
                    continue
                    
                # Skip very short words that are likely not meaningful (except common ones)
                if len(word) <= 2 and word.upper() not in ['OF', 'ST', 'DR', 'RD']:
                    continue
                    
                # Keep meaningful words
                filtered_words.append(word)
            
            return filtered_words
        
        # Get meaningful words for search
        meaningful_words = filter_meaningful_words(project_name)
        
        if not meaningful_words:
            # Fallback: if no meaningful words found, use original approach with full text
            return self._search_with_full_text(project_name, result, board_id, start_date)
        
        # Try meaningful words first
        matches = self._search_with_words(meaningful_words, board_id, start_date, project_name)
        
        # If no results with meaningful words, try with fewer words (remove less important ones)
        if not matches and len(meaningful_words) > 2:
            # Try with most important words (usually first 2-3 words)
            important_words = meaningful_words[:3]
            print(f"No results with all words, trying with important words: {important_words}")
            matches = self._search_with_words(important_words, board_id, start_date, project_name)
        
        # If still no results, fallback to similarity-based search
        if not matches:
            print("No results with word search, falling back to similarity search...")
            return self._fallback_similarity_search(project_name, result)
        
        # Process and return results
        result['matches'] = matches
        if matches:
            best_match = matches[0]
            result['exists'] = True
            result['type'] = 'existing'
            result['best_match'] = best_match
            result['similarity_score'] = best_match['similarity']
        
        return result

    def _search_with_words(self, words, board_id, start_date, original_project_name):
        """Helper method to search with specific words"""
        # Build rules for each word + date filter
        rules = []
        
        # Add a rule for each word to search for in the project title column
        for word in words:
            rules.append({
                "column_id": "text3__1",
                "compare_value": [word],
                "operator": "contains_text"
            })
        
        # Add date filter
        rules.append({
            "column_id": "date9__1",
            "compare_value": ["EXACT", start_date],
            "operator": "greater_than_or_equals"
        })
        
        # Convert rules to GraphQL format
        rules_str = ""
        for i, rule in enumerate(rules):
            if i > 0:
                rules_str += ","
            rules_str += f"""
              {{
                column_id: "{rule['column_id']}",
                compare_value: {json.dumps(rule['compare_value'])},
                operator: {rule['operator']}
              }}"""
        
        # Use Monday.com's built-in search with word-by-word approach
        query = f"""
        query {{
          boards(ids: [{board_id}]) {{
            items_page(
              query_params: {{
                rules: [{rules_str}],
                operator: and
              }},
              limit: 500
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
        
        print(f"=== SMART WORD SEARCH DEBUG ===")
        print(f"Original search term: {original_project_name}")
        print(f"Filtered words being searched: {words}")
        print("=================================")
        
        response = self.execute_query(query)
        
        if not response or "errors" in response:
            return []

        try:
            page = response["data"]["boards"][0]["items_page"]
            items = page.get("items", [])
        except (KeyError, IndexError, TypeError):
            return []
        
        # Process the results
        matches = []
        for item in items:
            if item.get("state") != "active":
                continue
            
            project_id = item["id"]
            project_name_value = item["name"]
            project_state = item.get("state", "unknown")
            
            # Extract the project title from column values
            project_title = project_name_value  # Default to name
            created_date = None
            
            for col in item.get("column_values", []):
                if col.get("id") == "text3__1" and col.get("text"):
                    project_title = col.get("text")
                elif col.get("id") == "date9__1" and col.get("text"):
                    created_date = col.get("text")
            
            # Calculate similarity score for ranking
            name_ratio = SequenceMatcher(None, original_project_name.lower(), project_name_value.lower()).ratio()
            title_ratio = SequenceMatcher(None, original_project_name.lower(), project_title.lower()).ratio() if project_title else 0
            similarity_score = max(name_ratio, title_ratio)
            
            matches.append({
                'id': project_id,
                'name': project_name_value,
                'title': project_title,
                'similarity': similarity_score,
                'state': project_state,
                'created_date': created_date
            })
        
        # Sort matches by similarity score (highest first)
        matches = sorted(matches, key=lambda x: x['similarity'], reverse=True)
        
        print(f"=== SMART SEARCH RESULTS ===")
        print(f"Words searched: {words}")
        print(f"Monday.com API matches: {len(matches)}")
        for match in matches:
            print(f"  - {match['title']} (similarity: {match['similarity']:.1%}, name: {match['name']})")
        
        return matches

    def _search_with_full_text(self, project_name, result, board_id, start_date):
        """Fallback search with full text"""
        print(f"Using fallback full-text search for: {project_name}")
        # Use the original single-phrase search as fallback
        # ... (implement the original single search query)
        return result

    def _fallback_similarity_search(self, project_name, result):
        """Final fallback using the old similarity-based approach"""
        print(f"Using final fallback similarity search for: {project_name}")
        # Get all projects and do local similarity matching
        projects, error = self.get_tapered_enquiry_projects()
        
        if error:
            result['error'] = error
            return result
        
        # ... (implement similarity matching logic)
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

    def get_board_columns(self, board_id):
        """
        Get all columns for a board.
        
        Args:
            board_id: ID of the board
            
        Returns:
            list: Column information
        """
        query = """
        query ($boardId: ID!) {
            boards(ids: [$boardId]) {
                columns {
                    id
                    title
                    type
                }
            }
        }
        """
        
        variables = {"boardId": board_id}
        result = self.execute_query(query, variables)
        
        if result and "data" in result and "boards" in result["data"]:
            return result["data"]["boards"][0]["columns"]
        
        return []

    def search_items_by_name_prefix(self, board_id, name_prefix):
        """
        Search for items in a board where the name starts with a specific prefix.
        
        Args:
            board_id: ID of the board to search in
            name_prefix: The prefix to search for (e.g., "16771")
            
        Returns:
            tuple: (list of matching items, error_message)
        """
        query = """
        query ($boardId: ID!) {
            boards(ids: [$boardId]) {
                items_page(limit: 500) {
                    items {
                        id
                        name
                    }
                }
            }
        }
        """
        
        variables = {"boardId": int(board_id)}
        result = self.execute_query(query, variables)
        
        if not result or "data" not in result:
            return None, "Failed to fetch items from board"
        
        try:
            items = result["data"]["boards"][0]["items_page"]["items"]
            
            # Filter items where name starts with the prefix
            matching_items = []
            for item in items:
                if item["name"].startswith(str(name_prefix)):
                    matching_items.append({
                        "id": item["id"],
                        "name": item["name"]
                    })
            
            return matching_items, None
            
        except (KeyError, IndexError) as e:
            return None, f"Error parsing response: {str(e)}"

    def search_item_by_name_query(self, board_id, search_term):
        """
        Search for items using Monday.com's query_params search.
        
        Args:
            board_id: ID of the board to search in
            search_term: The term to search for
            
        Returns:
            tuple: (list of matching items, error_message)
        """
        query = """
        query ($boardId: ID!, $searchTerm: String!) {
            boards(ids: [$boardId]) {
                items_page(
                    query_params: {
                        rules: [{
                            column_id: "name",
                            compare_value: [$searchTerm],
                            operator: any_of
                        }]
                    }
                ) {
                    items {
                        id
                        name
                    }
                }
            }
        }
        """
        
        variables = {
            "boardId": int(board_id),
            "searchTerm": str(search_term)
        }
        
        result = self.execute_query(query, variables)
        
        if not result or "data" not in result:
            return None, "Failed to fetch items from board"
        
        try:
            items = result["data"]["boards"][0]["items_page"]["items"]
            
            # Filter for exact matches only (since any_of might return partial matches)
            exact_matches = []
            for item in items:
                if item["name"] == str(search_term):
                    exact_matches.append({
                        "id": item["id"],
                        "name": item["name"]
                    })
            
            if exact_matches:
                return exact_matches, None
            else:
                return None, f"No item found with name '{search_term}'"
            
        except (KeyError, IndexError) as e:
            return None, f"Error parsing response: {str(e)}"

    # --- NEW METHOD (exact-name search that uses query_params) -------
    def get_item_id_by_exact_name(self, board_id: int, item_name: str):
        """
        Return the item id whose *name* exactly matches `item_name`
        on `board_id`.  None if not found.
        """
        # Monday.com's compare_value doesn't accept variables, so we inline the value
        query = f"""
        query {{
          boards(ids: [{int(board_id)}]) {{
            items_page(
              query_params: {{
                rules: [{{
                  column_id: "name",
                  compare_value: ["{str(item_name)}"],
                  operator: any_of
                }}]
              }},
              limit: 50
            ) {{
              items {{ id name }}
            }}
          }}
        }}
        """
        
        resp = self.execute_query(query)  # No variables needed
        
        if (
            resp and
            "data" in resp and
            resp["data"]["boards"] and
            resp["data"]["boards"][0]["items_page"]["items"]
        ):
            for itm in resp["data"]["boards"][0]["items_page"]["items"]:
                if itm["name"] == item_name:
                    return itm["id"]
        return None 
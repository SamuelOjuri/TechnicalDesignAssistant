import json
import requests
from difflib import SequenceMatcher
from flask import current_app
import itertools
from typing import Optional, BinaryIO

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
            Return a list of location / building words that are worth
            querying on Monday.com. Filters out punctuation, English stop words,
            and other non-meaningful tokens.
            """
            import re, string

            # English stop words (based on common lists like scikit-learn's)
            ENGLISH_STOP_WORDS = {
                # Generic English stop words
                'a', 'an', 'and', 'are', 'as', 'at', 'be', 'been', 'by', 'for', 
                'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 
                'the', 'to', 'was', 'were', 'will', 'with', 'the', 'this', 'but', 
                'they', 'have', 'had', 'what', 'said', 'each', 'which', 'she', 
                'do', 'how', 'their', 'if', 'up', 'out', 'many', 'then', 'them', 
                'these', 'so', 'some', 'her', 'would', 'make', 'like', 'into', 
                'him', 'time', 'two', 'more', 'go', 'no', 'way', 'could', 'my', 
                'than', 'been', 'call', 'who', 'sit', 'now', 'find', 'down', 
                'day', 'did', 'get', 'come', 'made', 'may', 'part'
            }

            # IMPROVED: Use a simpler approach that preserves meaningful punctuation
            # 1) Handle common abbreviations by removing the period
            text = re.sub(r'\b(St|Dr|Rd)\.\s*', r'\1 ', text)
            
            # 2) Split on punctuation but preserve apostrophes within words
            #    This regex splits on punctuation except apostrophes that are between word characters
            tokens = re.findall(r"\b\w+(?:'\w+)*\b", text)

            meaningful = []
            for word in tokens:
                upper = word.upper()
                lower = word.lower()

                # Skip pure house numbers (digits optionally followed by a letter)
                if re.fullmatch(r"\d+[A-Z]?", upper):
                    continue

                # UPDATED: Comprehensive UK postcode filtering
                # Special case: GIR 0AA
                if upper == "GIR":
                    continue
                    
                # UK Postcode patterns (based on GOV.UK official regex)
                uk_postcode_patterns = [
                    r"[A-Z][0-9]{1,2}",                    # M1, M60
                    r"[A-Z][A-HJKPSTUW][0-9]{1,2}",        # SW1, SW60 (second letter excludes I)
                    r"[A-Z][0-9][A-Z]",                    # W1T, M1A ← FIXES THE ISSUE
                    r"[A-Z][A-HJKPSTUW][0-9][A-Z]",        # WC1A, SW1A
                    r"[0-9][A-Z]{2}",                      # 1AL, 2AA (inward code)
                    r"0[A-Z]{2}"                           # 0AA (for GIR 0AA)
                ]
                
                # Check if token matches any UK postcode pattern
                if any(re.fullmatch(pattern, upper) for pattern in uk_postcode_patterns):
                    continue

                # Skip drawing references (letter(s) + numbers)
                if re.fullmatch(r"[A-Z]+\d+", upper):
                    continue

                # Skip English stop words (O(1) lookup)
                if lower in ENGLISH_STOP_WORDS:
                    continue

                # Skip very short tokens (len ≤ 2) unless whitelisted
                # Added more common abbreviations that should be preserved
                if len(word) <= 2 and upper not in {"OF", "ST", "DR", "RD"}:
                    continue

                meaningful.append(word)

            return meaningful
        
        # Get meaningful words for search
        meaningful_words = filter_meaningful_words(project_name)
        
        if not meaningful_words:
            # Fallback: if no meaningful words found, use original approach with full text
            return self._search_with_full_text(project_name, result, board_id, start_date)
        
        # Try meaningful words first
        matches = self._progressive_search(meaningful_words, board_id, start_date, project_name)
        
        # If still no results, fallback to similarity-based search
        if not matches:
            print("No results with word search, falling back to similarity search...")
            return self._fallback_similarity_search(project_name, result, similarity_threshold)
        
        # Process and return results
        result['matches'] = matches
        if matches:
            best_match = matches[0]
            result['exists'] = True
            result['type'] = 'existing'
            result['best_match'] = best_match
            result['similarity_score'] = best_match['similarity']
        
        return result

    # ------------------------------------------------------------------ #
    #  NEW helper: batch-query how many hits each token returns           #
    # ------------------------------------------------------------------ #
    def _get_word_hit_counts(self, words, board_id):
        """
        Ask Monday.com once for each word's hit-count and return a
        {word: count} mapping. Falls back to len(items) if total_items is
        not provided by the API.
        """
        # Build one GraphQL query with aliases (w0, w1 …) so we need only
        # ONE round-trip regardless of the token list length.
        blocks = []
        for idx, w in enumerate(words):
            alias = f"w{idx}"
            blocks.append(f"""
            {alias}: boards(ids: [{board_id}]) {{
              items_page(
                query_params: {{
                  rules: [{{
                    column_id: "text3__1",
                    compare_value: ["{w}"],
                    operator: contains_text
                  }}]
                }},
                limit: 50
              ) {{
                items {{ id }}
              }}
            }}""")
        query = "query {" + "".join(blocks) + "}"

        response = self.execute_query(query)
        counts = {w: 0 for w in words}        # default 0 if anything goes wrong
        try:
            data = response["data"]
            for idx, w in enumerate(words):
                page = data[f"w{idx}"][0]["items_page"]
                counts[w] = len(page.get("items", []))
        except Exception:
            # Graceful degradation – keep defaults
            pass
        return counts

    # ------------------------------------------------------------------ #
    #  Rank words from most-specific (fewest hits) to least              #
    # ------------------------------------------------------------------ #
    def _rank_words_by_specificity(self, words, board_id, start_date, original):
        """
        Order tokens using the batched hit counts. Only one API call.
        """
        counts = self._get_word_hit_counts(words, board_id)
        ranked = sorted(words, key=lambda w: counts.get(w, 1_000_000))
        if current_app and getattr(current_app, "debug", False):
            print(f"Word specificity order (hits): "
                  f"{[(w, counts[w]) for w in ranked]}")
        return ranked

    def _progressive_search(self, words, board_id, start_date, original):
        # Step-0: order tokens from most to least specific
        ordered = self._rank_words_by_specificity(words, board_id, start_date, original)

        # 1) try *all* words first (strict AND)
        hits = self._search_with_words(ordered, board_id, start_date, original)
        if hits:
            return hits

        # 2) Try all other non-empty subsets (except the full set, already tried)
        n = len(ordered)
        for r in range(n-1, 0, -1):
            for subset in itertools.combinations(ordered, r):
                hits = self._search_with_words(list(subset), board_id, start_date, original)
                if hits:
                    return hits

        return []

    # ------------------------------------------------------------------ #
    #  SEARCH HELPERS                                                    #
    # ------------------------------------------------------------------ #
    def _search_with_words(
        self,
        words,
        board_id,
        start_date,
        original_project_name,
        *,
        limit: int = 500,
        include_columns: bool = True,
    ):
        """
        Query Monday.com for items that match *all* tokens in `words`.

        Args:
            words (list[str])           : tokens to search for (AND logic).
            board_id (str | int)        : Monday board id.
            start_date (str)            : YYYY-MM-DD filter for Created column.
            original_project_name (str) : used only for debug / similarity calc.
            limit (int, optional)       : max records to ask Monday for (default 500).
            include_columns (bool)      : when False the column_values block is
                                          omitted to shrink the response payload.
        """
        # Build rules for each word + date filter
        rules = []
        for word in words:
            rules.append({
                "column_id": "text3__1",
                "compare_value": [word],
                "operator": "contains_text"
            })
        rules.append({
            "column_id": "date9__1",
            "compare_value": ["EXACT", start_date],
            "operator": "greater_than_or_equals"
        })

        # Convert rules to GraphQL string
        rules_str = ""
        for i, rule in enumerate(rules):
            if i:
                rules_str += ","
            rules_str += f"""
              {{
                column_id: "{rule['column_id']}",
                compare_value: {json.dumps(rule['compare_value'])},
                operator: {rule['operator']}
              }}"""

        # --- fields to request ------------------------------------------
        item_fields = """
                id
                name
                state
        """
        if include_columns:
            item_fields += """
                column_values(ids: ["text3__1", "date9__1"]) {
                  id
                  text
                  __typename
                  ... on MirrorValue {
                    display_value
                  }
                }
            """

        # --- final GraphQL query ----------------------------------------
        query = f"""
        query {{
          boards(ids: [{board_id}]) {{
            items_page(
              query_params: {{
                rules: [{rules_str}],
                operator: and
              }},
              limit: {int(limit)}
            ) {{
              cursor
              items {{{item_fields}
              }}
            }}
          }}
        }}
        """

        print("=== SMART WORD SEARCH DEBUG ===")
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
        
        query = f"""
        query {{
          boards(ids: {board_id}) {{
            items_page(
              query_params: {{
                rules: [{{
                  column_id: "text3__1",
                  compare_value: ["{project_name}"],
                  operator: contains_text
                }},
                {{
                  column_id: "date9__1", 
                  compare_value: ["EXACT", "{start_date}"],
                  operator: greater_than_or_equals
                }}]
              }},
              limit: 500
            ) {{
              items {{
                id
                name
                state
                column_values {{
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
        
        response = self.execute_query(query)
        
        if not response or "data" not in response:
            return result
            
        try:
            page = response["data"]["boards"][0]["items_page"]
            items = page.get("items", [])
        except (KeyError, IndexError, TypeError):
            return result
            
        matches = []
        for item in items:
            if item.get("state") != "active":
                continue
                
            project_id = item["id"]
            project_name_value = item["name"]
            project_state = item.get("state", "unknown")
            
            project_title = project_name_value
            created_date = None
            
            for col in item.get("column_values", []):
                if col.get("id") == "text3__1" and col.get("text"):
                    project_title = col.get("text")
                elif col.get("id") == "date9__1" and col.get("text"):
                    created_date = col.get("text")
                    
            name_ratio = SequenceMatcher(None, project_name.lower(), project_name_value.lower()).ratio()
            title_ratio = SequenceMatcher(None, project_name.lower(), project_title.lower()).ratio() if project_title else 0
            similarity_score = max(name_ratio, title_ratio)
            
            matches.append({
                'id': project_id,
                'name': project_name_value,
                'title': project_title,
                'similarity': similarity_score,
                'state': project_state,
                'created_date': created_date
            })
            
        matches = sorted(matches, key=lambda x: x['similarity'], reverse=True)
        result['matches'] = matches
        
        if matches:
            best_match = matches[0]
            result['exists'] = True
            result['type'] = 'existing'
            result['best_match'] = best_match
            result['similarity_score'] = best_match['similarity']
            
        return result

    def _fallback_similarity_search(self, project_name, result, similarity_threshold=0.50):
        """Final fallback using similarity-based approach with threshold filtering"""
        print(f"Using final fallback similarity search for: {project_name}")
        
        projects, error = self.get_tapered_enquiry_projects()
        
        if error:
            result['error'] = error
            return result
            
        matches = []
        for project in projects:
            project_id = project["id"]
            project_name_value = project["name"]
            project_state = project.get("state", "unknown")
            
            project_title = project_name_value
            created_date = None
            
            for col in project.get("column_values", []):
                if col.get("id") == "text3__1" and col.get("text"):
                    project_title = col.get("text")
                elif col.get("id") == "date9__1" and col.get("text"):
                    created_date = col.get("text")
                    
            name_ratio = SequenceMatcher(None, project_name.lower(), project_name_value.lower()).ratio()
            title_ratio = SequenceMatcher(None, project_name.lower(), project_title.lower()).ratio() if project_title else 0
            similarity_score = max(name_ratio, title_ratio)
            
            # Only include matches above the threshold
            if similarity_score >= similarity_threshold:
                matches.append({
                    'id': project_id,
                    'name': project_name_value,
                    'title': project_title,
                    'similarity': similarity_score,
                    'state': project_state,
                    'created_date': created_date
                })
            
        # Sort by similarity (best first)
        matches = sorted(matches, key=lambda x: x['similarity'], reverse=True)
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

    def upload_file_to_column(self, item_id: str, column_id: str, file_content: bytes, filename: str) -> Optional[dict]:
        """
        Upload a file to a specific column of an item.
        
        Args:
            item_id: ID of the item
            column_id: ID of the column (must be a 'file' type column)
            file_content: Binary content of the file
            filename: Name of the file
            
        Returns:
            dict: Response from Monday.com API or None if failed
        """
        # Prepare the GraphQL mutation
        mutation = """
        mutation ($file: File!) {
            add_file_to_column(item_id: %s, column_id: "%s", file: $file) {
                id
            }
        }
        """ % (item_id, column_id)
        
        # Prepare multipart form data
        files = {
            'variables[file]': (filename, file_content, 'application/octet-stream')
        }
        
        data = {
            'query': mutation,
        }
        
        # Use the file upload endpoint
        upload_url = "https://api.monday.com/v2/file"
        
        try:
            response = requests.post(
                upload_url,
                headers={
                    "Authorization": self.api_token,
                    "API-Version": "2023-10"
                },
                data=data,
                files=files,
                timeout=60  # Longer timeout for file uploads
            )
            
            if response.status_code == 200:
                result = response.json()
                if "errors" in result:
                    print(f"GraphQL Error uploading file: {result['errors']}")
                    return None
                return result
            else:
                print(f"HTTP Error uploading file: {response.status_code}")
                print(response.text)
                return None
                
        except Exception as e:
            print(f"Exception uploading file to Monday.com: {e}")
            return None 
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
    
    def check_project_exists(self, project_name):
        """
        Check if a project with a similar name already exists in Monday.com.
        
        Args:
            project_name: Name of the project to search for
            
        Returns:
            dict: Search results
        """
        query = """
        query {
            boards(ids: [1825117125]) {
                name
                id
                items_page(limit: 500) {
                    items {
                        id
                        name
                        column_values(ids: ["text3__1"]) {
                            id
                            text
                        }
                    }
                }
            }
        }
        """
        
        result = self.execute_query(query)
        
        if not result or "data" not in result or "boards" not in result["data"] or len(result["data"]["boards"]) == 0:
            return {"exists": False, "matches": [], "error": "API error"}
        
        board = result["data"]["boards"][0]
        matches = []
        
        # Find items with similar names
        if "items_page" in board and "items" in board["items_page"]:
            for item in board["items_page"]["items"]:
                # Check name similarity
                ratio = SequenceMatcher(None, project_name.lower(), item["name"].lower()).ratio()
                
                # Also check text3__1 column (Project Name) if available
                project_title = item["name"]  # Default to name
                for col in item.get("column_values", []):
                    if col.get("id") == "text3__1" and col.get("text"):
                        project_title = col.get("text")
                        break
                
                # Use the higher similarity score
                title_ratio = SequenceMatcher(None, project_name.lower(), project_title.lower()).ratio() if project_title else 0
                best_ratio = max(ratio, title_ratio)
                
                if best_ratio > 0.6:  # Threshold for considering a match
                    matches.append({
                        "id": item["id"],
                        "name": item["name"],
                        "title": project_title,
                        "similarity": best_ratio
                    })
        
        # Sort matches by similarity
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Limit to top 5 matches
        matches = matches[:5]
        
        return {
            "exists": len(matches) > 0,
            "matches": matches
        }
    
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
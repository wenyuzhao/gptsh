from agentia.plugins import tool, Plugin
from typing import Annotated, override
import os
from tavily import TavilyClient

from autosh.plugins import Banner


class SearchPlugin(Plugin):
    @override
    async def init(self):
        if "tavily_api_key" in self.config:
            key = self.config["tavily_api_key"]
        elif "TAVILY_API_KEY" in os.environ:
            key = os.environ["TAVILY_API_KEY"]
        else:
            raise ValueError("Please set the TAVILY_API_KEY environment variable.")
        self.__tavily = TavilyClient(api_key=key)

    @tool(metadata={"banner": Banner("WEB SEARCH", text_key="query")})
    async def web_search(
        self,
        query: Annotated[
            str, "The search query. Please be as specific and verbose as possible."
        ],
    ):
        """
        Perform web search on the given query.
        Returning the top related search results in json format.
        When necessary, you need to combine this tool with the get_webpage_content tools (if available), to browse the web in depth by jumping through links.
        """
        tavily_results = self.__tavily.search(
            query=query,
            search_depth="advanced",
            # max_results=10,
            include_answer=True,
            include_images=True,
            include_image_descriptions=True,
        )
        return tavily_results

    @tool(metadata={"banner": Banner("NEWS SEARCH", text_key="query")})
    async def news_search(
        self,
        query: Annotated[
            str, "The search query. Please be as specific and verbose as possible."
        ],
    ):
        """
        Perform news search on the given query.
        Returning the top related results in json format.
        """

        tavily_results = self.__tavily.search(
            query=query,
            search_depth="advanced",
            topic="news",
            # max_results=10,
            include_answer=True,
            include_images=True,
            include_image_descriptions=True,
        )
        return tavily_results

    @tool(metadata={"banner": Banner("FINANCE SEARCH", text_key="query")})
    async def finance_search(
        self,
        query: Annotated[
            str, "The search query. Please be as specific and verbose as possible."
        ],
    ):
        """
        Search for finance-related news and information on the given query.
        Returning the top related results in json format.
        """

        tavily_results = self.__tavily.search(
            query=query,
            search_depth="advanced",
            topic="finance",
            # max_results=10,
            include_answer=True,
            include_images=True,
            include_image_descriptions=True,
        )
        return tavily_results

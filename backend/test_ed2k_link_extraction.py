# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace

from media_candidate_service import analyze_media_candidate
from message_cleaner_service import clean_message_text
from scrape_link_collector_service import extract_link_candidates
from utils import extract_resource_links_from_text


ED2K_URL = (
    "ed2k://|file|Life.Without.Principle.2011.1080p.mkv|32022289043|"
    "B63802980965F9CBF7E2B2634F8FD44A|/"
)


class Ed2kLinkExtractionTests(unittest.TestCase):
    def test_code_formatted_ed2k_is_extracted_without_changing_existing_links(self):
        message = SimpleNamespace(
            text=(
                "夺命金 (2011) 1080p\n"
                f"链接：115云下载：`{ED2K_URL}`\n"
                "备用：magnet:?xt=urn:btih:abcdef\n"
                "https://115.com/s/abc"
            ),
            entities=None,
            reply_markup=None,
        )

        candidates = extract_link_candidates(message)

        self.assertEqual(
            candidates["direct_resource_links"],
            ["https://115.com/s/abc", ED2K_URL, "magnet:?xt=urn:btih:abcdef"],
        )

    def test_code_formatted_ed2k_is_not_duplicated_or_stored_with_backticks(self):
        text = f"夺命金 (2011) 1080p\n链接：`{ED2K_URL}`"

        cleaned = clean_message_text(title="夺命金", raw_text=text)
        candidate = analyze_media_candidate(raw_text=text, links=[ED2K_URL])
        extracted = extract_resource_links_from_text(text)

        self.assertTrue(cleaned.has_resource_url)
        self.assertEqual([item.url for item in cleaned.urls if item.kind == "resource"], [ED2K_URL])
        self.assertEqual(candidate.resource_links, [ED2K_URL])
        self.assertEqual(extracted, [{"url": ED2K_URL, "type": "ed2k", "password": None}])


if __name__ == "__main__":
    unittest.main()

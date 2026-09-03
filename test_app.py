import unittest

from app import app, instructions, shelters, parse_area_warnings


class ShelterRegisterTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
        self.original_count = len(shelters)

    def tearDown(self):
        del shelters[self.original_count:]

    def test_register_with_name_shows_success_message(self):
        response = self.client.post('/shelter_register', data={'name': '新しい避難所'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('登録しました', response.get_data(as_text=True))

    def test_register_without_name_shows_error_message(self):
        response = self.client.post('/shelter_register', data={'name': ''})

        self.assertEqual(response.status_code, 200)
        self.assertIn('避難所名を登録してください', response.get_data(as_text=True))


class WeatherWarningParserTests(unittest.TestCase):
    def test_parse_real_jma_warning_payload(self):
        payload = [{
            "reportDatetime": "2026-09-02T11:17:00+09:00",
            "headlineText": "土砂災害警戒情報",
            "warning": {
                "class20Items": [{
                    "areaCode": "1420500",
                    "kinds": [{
                        "code": "49",
                        "status": "発表"
                    }]
                }]
            }
        }]

        warnings, report_datetime, headline = parse_area_warnings(payload)

        self.assertEqual(report_datetime, "2026-09-02T11:17:00+09:00")
        self.assertEqual(headline, "土砂災害警戒情報")
        self.assertEqual(warnings[0]["name"], "土砂災害警戒情報")
        self.assertEqual(warnings[0]["status"], "発表")

    def test_parse_warning_without_code_uses_headline(self):
        payload = [{
            "reportDatetime": "2019-06-21T11:05:00+09:00",
            "headlineText": "土砂災害警戒情報",
            "warning": {
                "class20Items": [{
                    "areaCode": "4620100",
                    "kinds": [{
                        "code": "3",
                        "status": "発表"
                    }]
                }]
            }
        }]

        warnings, _, headline = parse_area_warnings(payload)

        self.assertEqual(headline, "土砂災害警戒情報")
        self.assertEqual(warnings[0]["name"], "土砂災害警戒情報")


class BoardInstructionTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
        self.original_instructions = instructions.copy()

    def tearDown(self):
        instructions[:] = self.original_instructions

    def test_create_instruction_from_board_form(self):
        response = self.client.post('/board', data={
            'target': '住民',
            'content': '北地区の住民へ避難を呼びかけます',
            'district': '北地区'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('北地区の住民へ避難を呼びかけます', response.get_data(as_text=True))

    def test_instruction_list_shows_target_and_staff_instruction(self):
        response = self.client.post('/board', data={
            'target': '職員',
            'content': '中央地区の職員へ現地確認を依頼します',
            'district': '中央地区'
        })

        page = response.get_data(as_text=True)

        self.assertIn('中央地区', page)
        self.assertIn('職員', page)
        self.assertIn('中央地区の職員へ現地確認を依頼します', page)


if __name__ == '__main__':
    unittest.main()

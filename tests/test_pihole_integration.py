
import pytest
import requests
from tests import utils

@pytest.mark.skip("Not testing this right now")
def test_get_all_queries(mocker, app):
    from app.service_integration_api import PiholeConsumer

    pihole_consumer = PiholeConsumer("test-domain", "test_auth_token")

    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "value"}

    mocker.patch('requests.get', return_value=mock_response)

    from_datetime, until_datetime = utils.generate_random_from_until_datetimes()
    from_ts = utils.datetime_to_unix_timestamp(from_datetime)
    until_ts = utils.datetime_to_unix_timestamp(until_datetime)

    result = pihole_consumer.get_all_queries_ts(
        from_ts, until_ts)

    requests.get.assert_called_once_with(
        "http://test-domain/admin/api.php", params={"auth": "test_auth_token",
                                                    "getAllQueries": "1",
                                                    "from": str(from_ts),
                                                    "until": str(until_ts)})

    assert result == {"key": "value"}

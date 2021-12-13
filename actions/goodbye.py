# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from actions.api import SingletonApiClass


class ActionGoodbyeWorld(Action):

    def name(self) -> Text:
        return "action_goodbye_world"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        client_result = SingletonApiClass().get_result()
        dispatcher.utter_message(text=f"Goodbye result! {client_result}")

        return []

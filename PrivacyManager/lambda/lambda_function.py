# Portland State University Capstone Fall-Winter 2021
# Privacy Manager skill to allow users to delegate access to specific recordings and files to other users

import logging
import ask_sdk_core.utils as ask_utils
import os

from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response

from ask_sdk_model.interfaces.audioplayer import AudioItem, Stream, PlayDirective, PlayBehavior

from ask_sdk_s3.adapter import S3Adapter

from utils import read_file, does_user_exist, does_file_exists, create_new_user, sign_in, sign_out, \
                  is_logged_in, get_current_user, make_request, add_recording, list_requests, \
                  create_presigned_url, accept_request, deny_request, list_access_from, list_all_access, \
                  revoke_access, list_file_names, list_preferences

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
s3_adapter = S3Adapter(bucket_name=os.environ["S3_PERSISTENCE_BUCKET"])

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        if is_logged_in(handler_input):
            current_user = get_current_user(handler_input)
            intro = f"Hi {current_user}. If this is not you, please say 'log out'."
            intro += " Otherwise, What would you like to do? Your options are as follows: One. List pending requests. Two. Review my access permissions. Three. Request access from a user. Four. Accept a request. Five. Deny access to a user. Six. Revoke access from a user. Seven. List access permissions from a specific user. Eight. List all access granted."
        else:
            intro = "Welcome to your Privacy Manager! If you are new, please say 'create new user' and then the name you'd like to have. Otherwise say 'Log into' followed by your username."

        return (
            handler_input.response_builder
                .speak(intro)
                .ask(intro)
                .response
        )

class LoginIntentHandler(AbstractRequestHandler):
    """Handler for user login function."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("Login")(handler_input)
        
    def handle(self, handler_input):
        login_username = handler_input.request_envelope.request.intent.slots['user_name'].value
        if does_user_exist(login_username):
            sign_in(handler_input, login_username)
            speak_output = "You are signed in as " + login_username + ". What would you like to do? Your options are as follows: One. List pending requests. Two. Review my access permissions. Three. Request access from a user. Four. Accept a request. Five. Deny access to a user. Six. Revoke access from a user. Seven. List access permissions from a specific user. Eight. List all access granted."
        else:
            speak_output = "I couldn't find a user by the name of " + login_username + ". If I misheard you, please restate 'log into' followed by your username. Otherwise, I can create a new user named " + login_username + ", if you'd like? If so, please say 'create user " + login_username + "'."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class LogoutIntentHandler(AbstractRequestHandler):
    """Handler for user logout function."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("Logout")(handler_input)
        
    def handle(self, handler_input):
        if is_logged_in(handler_input):
            sign_out(handler_input)
            speak_output = "You are now logged out. If you would like to log in, please say 'Log into' followed by the username. Otherwise, I can create a new user: say 'create user' followed by a username."
        else:
            speak_output = "No user is currently logged in. If you would like to log in, please say 'Log into' followed by the username. Otherwise, I can create a new user: say 'create user' followed by a username."
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class CreateNewUserIntentHandler(AbstractRequestHandler):
    """Handler for new user creation dialog."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("CreateNewUser")(handler_input)
    
    def handle(self, handler_input):
        new_user = handler_input.request_envelope.request.intent.slots["user_name"].value

        if does_user_exist(new_user):
            speak_output = "I'm sorry. That username is already taken. Please state a different name for the new user. Say 'create a user named' and then the username."
        else:
            create_new_user(new_user)
            sign_in(handler_input, new_user)
            speak_output = "Your user account has been created with the name " + new_user + ". I have signed you in already. What would you like to do? Your options are as follows: One. List pending requests. Two. Review my access permissions. Three. Request access from a user. Four. Accept a request. Five. Deny access to a user. Six. Revoke access from a user. Seven. List access permissions from a specific user. Eight. List all access granted."
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class MakeRequestIntentHandler(AbstractRequestHandler):
    """Handler for requesting access from another user."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("MakeRequest")(handler_input)
    
    def handle(self, handler_input):
        if not is_logged_in(handler_input):
            speak_output = "Sorry, but you need to be logged in to request access from another user. "
        else:
            requester = get_current_user(handler_input)
            slots = handler_input.request_envelope.request.intent.slots
            requestee = slots['user_name'].value
            access_type = slots['request_type'].value
            reason = slots['reason'].value
            
            if does_user_exist(requestee):
                response = make_request(requester, requestee, access_type, reason)
                if(response):
                    speak_output = "I have put in your " + reason + " request to " + access_type + " using " + requestee + "'s recordings. "
                else:
                    speak_output = "I had trouble doing that. It's possible you might have a request already made to " + requestee + ". "
            else:
                speak_output = "I couldn't find a user who goes by " + requestee + ". "
            
        speak_output = speak_output + "What would you like to do?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class AcceptRequestIntentHandler(AbstractRequestHandler):
    """Handler for accepting an access request from another user."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AcceptRequest")(handler_input)
    
    def handle(self, handler_input):
        if not is_logged_in(handler_input):
            speak_output = "Sorry, but you need to be logged in to accept an access request from another user. "
        else:
            requestee = get_current_user(handler_input)
            slots = handler_input.request_envelope.request.intent.slots
            requester = slots['user_name'].value
            file_name = slots['file_name'].value
            if does_user_exist(requester):
                all_files = False
                if file_name == "all files":
                    file_name = None
                    all_files = True
                
                response = accept_request(requestee, requester, file_name)
                
                if response:
                    reason = response["reason"]
                    request_type = response["request_type"]
                    if all_files:
                        speak_output = "You have granted " + requester + " " + reason + " access to " + request_type + " using your recordings. "
                    else:
                        speak_output = "You have granted " + requester + " " + reason + " access to " + request_type + " using your recording called " + file_name + ". "
                else:
                    speak_output = "I couldn't find a request from " + requester + " to accept. "
            else:
                speak_output = "Sorry, I couldn't find a user who goes by " + requester + ". "
        
        speak_output = speak_output + "What would you like to do?"
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )
    
class DenyRequestIntentHandler(AbstractRequestHandler):
    """Handler for denying an access request from another user."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("DenyRequest")(handler_input)

    def handle(self, handler_input):
        if not is_logged_in(handler_input):
            speak_output = "Sorry, but you need to be logged in to deny an access request from another user. "
        else:    
            requestee = get_current_user(handler_input)
            slots = handler_input.request_envelope.request.intent.slots
            requester = slots['user_name'].value
            if does_user_exist(requester):
                response = deny_request(requestee, requester)
                if response:
                    speak_output = "You have denied " + requester + " from accessing your recordings. "
                else:
                    speak_output = "I couldn't find a request from " + requester + " to deny. "
            else:
                speak_output = "Sorry, I couldn't find a user who goes by " + requester + ". "
        
        speak_output = speak_output + "What would you like to do?"
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )
    
class HasAccessIntentHandler(AbstractRequestHandler):
    """Handler for determining whether or not the user has access to another user's data."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("HasAccess")(handler_input)
    
    def handle(self, handler_input):
        if not is_logged_in(handler_input):
            speak_output = "Sorry, but you need to be logged in to check for access from another user. "
        else:
            requester = get_current_user(handler_input)
            slots = handler_input.request_envelope.request.intent.slots
            requestee = slots['user_name'].value
            if does_user_exist(requestee):
                response = list_access_from(requester, requestee)
                speech_lines = []
                for access_tuple in response:
                    file = access_tuple[0]
                    if file == "all_files":
                        file = "all files"
                    
                    for access_object in access_tuple[1]:
                        speech_lines.append(f"{requestee} has given you {access_object['request_type']} access to {file} for {access_object['reason']} projects.")
                
                if len(speech_lines) > 0:
                    speak_output = " ".join(speech_lines)
                else:
                    speak_output = "It seems like " + requestee + " hasn't given you access to any of their recordings yet."
            else:
                speak_output = "Sorry, I couldn't find a user who goes by " + requestee + "."
        
        speak_output = speak_output + " What would you like to do?"
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class AllAccessIntentHandler(AbstractRequestHandler):
    """Handler for determining all data from other users that the current user has access to."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AllAccess")(handler_input)
    
    def handle(self, handler_input):
        if not is_logged_in(handler_input):
            speak_output = "Sorry, but you need to be logged in to check for access from another user. "
        else:
            requester = get_current_user(handler_input)
            response = list_all_access(requester)
            speech_lines = []
            for requestee in response.keys():
                for access_tuple in response[requestee]:
                    file = access_tuple[0]
                    if file == "all_files":
                        file = "all files"
                    
                    for access_object in access_tuple[1]:
                        speech_lines.append(f"{requestee} has given you {access_object['request_type']} access to {file} for {access_object['reason']} projects.")
            
            if len(speech_lines) > 0:
                speak_output = " ".join(speech_lines)
            else:
                speak_output = "It seems like no one has given you access to their recordings yet."
        
        speak_output = speak_output + " What would you like to do?"
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class ListPreferencesIntentHandler(AbstractRequestHandler):
    """Handler for listing out all current privacy preferences in the user's account."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ListPreferences")(handler_input)
    
    def handle(self, handler_input):
        if not is_logged_in(handler_input):
            speak_output = "Sorry, but you need to be logged in to list your privacy preferences. "
        else:
            user = get_current_user(handler_input)
            response = list_preferences(user)
            if len(response) > 0:
                speak_output = " ".join(response)
            else:
                speak_output = "Hmm... It doesn't seem like you've given anyone access to your files."
        
        speak_output = speak_output + " What would you like to do?"
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class RevokeAccessIntentHandler(AbstractRequestHandler):
    """Handler for revoking another user's access to the current user's data."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("RevokeAccess")(handler_input)
    
    def handle(self, handler_input):
        if not is_logged_in(handler_input):
            speak_output = "Sorry, but you need to be logged in to revoke access from another user. "
        else:
            requestee = get_current_user(handler_input)
            slots = handler_input.request_envelope.request.intent.slots
            requester = slots['user_name'].value
            if does_user_exist(requester):
                if slots['request_type'].value:
                    access_type = slots['request_type'].value
                else:
                    access_type = None
                
                if slots['reason'].value:
                    reason = slots['reason'].value
                else:
                    reason = None
                
                response = revoke_access(requestee, requester, access_type, reason)
                permissions_revoked = len(response)
                
                if permissions_revoked > 0:
                    speak_output = "I have revoked " + str(permissions_revoked) + " permissions from " + requester + "."
                else:
                    speak_output = "I couldn't find any permissions to revoke from " + requester + "."
            
            else:
                speak_output = "Sorry, I couldn't find a user who goes by " + requester + "."
        
        speak_output = speak_output + " What would you like to do?"
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class ListCurrentRequestsIntentHandler(AbstractRequestHandler):
    """Handler for listing all pending requests to the current user."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ListRequests")(handler_input)
    
    def handle(self, handler_input):
        if is_logged_in(handler_input):
            requests = list_requests(get_current_user(handler_input))
            speak_output = "Your current requests are: "
            if len(requests) > 0:
                for req in requests:
                    speak_output += req
            else:
                speak_output = "Hmm... There don't seem to be any requests for your data."
        else:
            speak_output = "You are currently not signed in. Please sign in to view your privacy requests."
        
        speak_output = speak_output + " What would you like to do?"
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class ListFilesIntentHandler(AbstractRequestHandler):
    """Handler for listing the filenames of all recordings currently in the user's directory."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ListFiles")(handler_input)
    
    def handle(self, handler_input):
        if is_logged_in(handler_input):
            current_user = get_current_user(handler_input)
            recordings_key = f"Media/users/{current_user}/recordings/"
            recordings = list_file_names(recordings_key)
            
            if len(recordings) > 0:
                speak_output = "Your recordings are: "
                for file in recordings:
                    speak_output += f" {file},"
                speak_output = speak_output[:-1]
            else:
                speak_output = "I'm sorry, you currently do not have any recordings"
        
        else:
            speak_output = "You are currently not signed in. Please sign in to view your recordings"
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class AddRecordingIntentHandler(AbstractRequestHandler):
    """Handler for moving recordings from a sample folder into a user folder. Mostly for testing, demonstration purposes."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AddRecording")(handler_input)
    
    def handle(self, handler_input):
        current_user = get_current_user(handler_input)
        file_name = handler_input.request_envelope.request.intent.slots['file_name'].value + ".m4a"
        if does_file_exists(file_name, "Media/sample_recordings/"):
            add_recording(current_user, file_name)
            speak_output = "The recording has been added to your profile. "

        else:
            speak_output = "I'm sorry. I could not locate the recording you requested."
        
        speak_output = speak_output + "What would you like to do?"
        #new_user = handler_input.request_envelope.request.intent.slots["user_name"].value
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class PlayRecordingIntentHandler(AbstractRequestHandler):
    """Handler for audio playback of files within the user folder.
    IMPORTANT NOTE: audio playback not supported in the SDK, only on a real device."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("PlayRecording")(handler_input)
    
    def handle(self, handler_input):
        current_user = get_current_user(handler_input)
        file_name = handler_input.request_envelope.request.intent.slots['file_name'].value
        recording_key = f"Media/users/{current_user}/recordings/{file_name}.m4a"
        if does_file_exists(file_name, f"Media/users/{current_user}/recordings/"):
            recording_url = create_presigned_url(recording_key)
            handler_input.response_builder.add_directive(
                PlayDirective(play_behavior=PlayBehavior.REPLACE_ALL,
                    audio_item=AudioItem(stream=Stream(token="1234AAAABBBBCCCCCDDDDEEEEEFFFF",
                    url=recording_url, offset_in_milliseconds=10, expected_previous_token=None))))
        
        return (
            handler_input.response_builder.response
        )

# Just for testing purposes
class ReadFileIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ReadFile")(handler_input)
        
    def handle(self, handler_input):
        # testing this
        speak_output = read_file("Media/test.txt")
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
            )
    
class HelloWorldIntentHandler(AbstractRequestHandler):
    """Handler for Hello World Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("HelloWorldIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Hello test"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Your options are as follows: One. List pending requests. Two. Review my access permissions. Three. Request access from a user. Four. Accept a request. Five. Deny access to a user. Six. Revoke access from a user. Seven. List access permissions from a specific user. Eight. List all access granted."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Goodbye!"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )

class FallbackIntentHandler(AbstractRequestHandler):
    """Single handler for Fallback Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In FallbackIntentHandler")
        speech = "Hmm, I'm not sure. Your options are as follows: One. List pending requests. Two. Review my access permissions. Three. Request access from a user. Four. Accept a request. Five. Deny access to a user. Six. Revoke access from a user. Seven. List access permissions from a specific user. Eight. List all access granted."
        reprompt = "I didn't catch that. What can I help you with?"

        return handler_input.response_builder.speak(speech).ask(reprompt).response

class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

# The SkillBuilder object acts as the entry point for the skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.

sb = CustomSkillBuilder(persistence_adapter=s3_adapter)

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(HelloWorldIntentHandler())
sb.add_request_handler(CreateNewUserIntentHandler())
sb.add_request_handler(LoginIntentHandler())
sb.add_request_handler(LogoutIntentHandler())
sb.add_request_handler(MakeRequestIntentHandler())
sb.add_request_handler(AcceptRequestIntentHandler())
sb.add_request_handler(DenyRequestIntentHandler())
sb.add_request_handler(HasAccessIntentHandler())
sb.add_request_handler(AllAccessIntentHandler())
sb.add_request_handler(RevokeAccessIntentHandler())
sb.add_request_handler(AddRecordingIntentHandler())
sb.add_request_handler(ListFilesIntentHandler())
sb.add_request_handler(ListCurrentRequestsIntentHandler())
sb.add_request_handler(ListPreferencesIntentHandler())
sb.add_request_handler(PlayRecordingIntentHandler())
sb.add_request_handler(ReadFileIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
import json
import os
import subprocess
import uuid
from subprocess import Popen
import random
from story.utils import *


class Story:
    def __init__(
        self, story_start, context="", seed=None, game_state=None, upload_story=False
    ):
        self.story_start = story_start
        self.context = context
        self.rating = -1
        self.upload_story = upload_story

        # list of actions. First action is the prompt length should always equal that of story blocks
        self.actions = []

        # list of story blocks first story block follows prompt and is intro story
        self.results = []

        # Only needed in constrained/cached version
        self.seed = seed
        set_seed(seed)
        self.choices = []
        self.possible_action_results = None
        self.uuid = None

        if game_state is None:
            game_state = dict()
        self.game_state = game_state
        self.memory = 20

    def __del__(self):
        if self.upload_story:
            self.save_to_storage()
            console_print("Game saved.")
            console_print(
                "To load the game, type 'load' and enter the following ID: " + self.uuid
            )

    def init_from_dict(self, story_dict):
        self.story_start = story_dict["story_start"]
        self.seed = story_dict["seed"]
        set_seed(seed)
        self.actions = story_dict["actions"]
        self.results = story_dict["results"]
        self.choices = story_dict["choices"]
        self.possible_action_results = story_dict["possible_action_results"]
        self.game_state = story_dict["game_state"]
        self.context = story_dict["context"]
        self.uuid = story_dict["uuid"]

        if "rating" in story_dict.keys():
            self.rating = story_dict["rating"]
        else:
            self.rating = -1

    def initialize_from_json(self, json_string):
        story_dict = json.loads(json_string)
        self.init_from_dict(story_dict)

    def add_to_story(self, action, story_block):
        self.actions.append(action)
        self.results.append(story_block)
        if len(self.actions) > 10000:
            self.actions.pop(1)
            self.results.pop(1)

    def latest_result(self, mem_ind=None, sample=False):
        mem_ind = mem_ind if mem_ind is not None else self.memory
        if len(self.results) < 2:
            latest_results = [self.story_start]
        else:
            latest_results = [self.context]
        latest_result = ""

        all_inds = list(range(len(self.results)))
        if sample:
            n = min(mem_ind, len(all_inds) - 1)
            n = max(0, n)
            inds = random.sample(all_inds, n)
            if len(self.results):
                inds += [len(all_inds) - 1]  # Always include the last prompt too
        elif mem_ind < len(self.results):
            # When we have to much history we will take the last 10, and sample randomly from the rest
            # first take last mem_ind//2
            first = all_inds[: -mem_ind // 2]
            last = all_inds[-mem_ind // 2 :]
            inds = random.sample(first, mem_ind // 2) + last
        else:
            inds = range(len(self.results))
        logger.debug("Using history indices %s", repr(inds))
        inds = sorted(set(inds))
        for i in inds:
            latest_result += self.actions[i] + self.results[i]
        return latest_results + [latest_result]

    def __str__(self):
        story_list = [self.story_start]
        for i in range(len(self.results)):
            story_list.append("\n" + self.actions[i] + "\n")
            story_list.append("\n" + self.results[i])

        return "".join(story_list)

    # delet this
    def to_json(self):
        story_dict = {}
        story_dict["story_start"] = self.story_start
        story_dict["seed"] = self.seed
        story_dict["actions"] = self.actions
        story_dict["results"] = self.results
        story_dict["choices"] = self.choices
        story_dict["possible_action_results"] = self.possible_action_results
        story_dict["game_state"] = self.game_state
        story_dict["context"] = self.context
        story_dict["uuid"] = self.uuid
        story_dict["rating"] = self.rating

        return json.dumps(story_dict)

    def save_to_local(self, save_name):
        self.uuid = str(uuid.uuid1())
        story_json = self.to_json()
        file_name = "AIDungeonSave_" + save_name + ".json"
        f = open(file_name, "w")
        f.write(story_json)
        f.close()

    def load_from_local(self, save_name):
        file_name = "AIDungeonSave_" + save_name + ".json"
        print("Save ID that can be used to load game is: ", self.uuid)

        with open(file_name, "r") as fp:
            game = json.load(fp)
        self.init_from_dict(game)

    def save_to_storage(self):
        self.uuid = str(uuid.uuid1())

        story_json = self.to_json()
        file_name = "story" + str(self.uuid) + ".json"
        f = open(file_name, "w")
        f.write(story_json)
        f.close()

        return self.uuid

    def load_from_storage(self, story_id):

        file_name = "story" + story_id + ".json"
        exists = os.path.isfile(file_name)

        if exists:
            with open(file_name, "r") as fp:
                game = json.load(fp)
            self.init_from_dict(game)
            return str(self)
        else:
            return "Error save not found."


class StoryManager:
    def __init__(self, generator):
        self.generator = generator
        self.story = None

    def start_new_story(
        self, story_prompt, context="", game_state=None, upload_story=False
    ):
        block = self.generator.generate([context, story_prompt])
        block = cut_trailing_sentence(block)
        self.story = Story(
            context + story_prompt + block,
            context=context,
            game_state=game_state,
            upload_story=upload_story,
        )
        return self.story

    def load_new_story(self, story_id):
        file_name = "story" + story_id + ".json"
        exists = os.path.isfile(file_name)

        if exists:
            with open(file_name, "r") as fp:
                game = json.load(fp)
            self.story = Story("")
            self.story.init_from_dict(game)
            return str(self.story)
        else:
            return "Error: save not found."

    def load_story(self, story, from_json=False):
        if from_json:
            self.story = Story("")
            self.story.initialize_from_json(story)
        else:
            self.story = story
        return str(story)

    def json_story(self):
        return self.story.to_json()

    def story_context(self, mem_ind=None, sample=False, include_prompt=True):
        s = self.story.latest_result(mem_ind=mem_ind, sample=sample)
        if not include_prompt:
            s = s[1:]
        logger.info(
            "story_context mem_ind={}, sample={}, include_prompt={}".format(
                mem_ind, sample, include_prompt
            )
        )
        return s


class UnconstrainedStoryManager(StoryManager):
    def act(self, action_choice):

        result = self.generate_result(action_choice)
        self.story.add_to_story(action_choice, result)
        return result

    def generate_result(self, action):
        block = self.generator.generate(self.story_context() + [action])
        return block


class ConstrainedStoryManager(StoryManager):
    def __init__(self, generator, action_verbs_key="classic"):
        super().__init__(generator)
        self.action_phrases = get_action_verbs(action_verbs_key)
        self.cache = False
        self.cacher = None
        self.seed = None

    def enable_caching(
        self, credentials_file=None, seed=42, bucket_name="dungeon-cache"
    ):
        self.cache = True
        self.cacher = Cacher(credentials_file, bucket_name)
        self.seed = seed

    def start_new_story(self, story_prompt, context="", game_state=None):
        if self.cache:
            return self.start_new_story_cache(story_prompt, game_state=game_state)
        else:
            return super().start_new_story(
                story_prompt, context=context, game_state=game_state
            )

    def start_new_story_generate(self, story_prompt, game_state=None):
        super().start_new_story(story_prompt, game_state=game_state)
        self.story.possible_action_results = self.get_action_results()
        return self.story.story_start

    def start_new_story_cache(self, story_prompt, game_state=None):

        response = self.cacher.retrieve_from_cache(self.seed, [], "story")
        if response is not None:
            story_start = story_prompt + response
            self.story = Story(story_start, seed=self.seed)
            self.story.possible_action_results = self.get_action_results()
        else:
            story_start = self.start_new_story_generate(
                story_prompt, game_state=game_state
            )
            self.story.seed = self.seed
            self.cacher.cache_file(self.seed, [], story_start, "story")

        return story_start

    def load_story(self, story, from_json=False):
        story_string = super().load_story(story, from_json=from_json)
        return story_string

    def get_possible_actions(self):
        if self.story.possible_action_results is None:
            self.story.possible_action_results = self.get_action_results()

        return [
            action_result[0] for action_result in self.story.possible_action_results
        ]

    def act(self, action_choice_str):

        try:
            action_choice = int(action_choice_str)
        except:
            print("Error invalid choice.")
            return None, None

        if action_choice < 0 or action_choice >= len(self.action_phrases):
            print("Error invalid choice.")
            return None, None

        self.story.choices.append(action_choice)
        action, result = self.story.possible_action_results[action_choice]
        self.story.add_to_story(action, result)
        self.story.possible_action_results = self.get_action_results()
        return result, self.get_possible_actions()

    def get_action_results(self):
        if self.cache:
            return self.get_action_results_cache()
        else:
            return self.get_action_results_generate()

    def get_action_results_generate(self):
        action_results = [
            self.generate_action_result(self.story_context(), phrase)
            for phrase in self.action_phrases
        ]
        return action_results

    def get_action_results_cache(self):
        response = self.cacher.retrieve_from_cache(
            self.story.seed, self.story.choices, "choices"
        )

        if response is not None:
            print("Retrieved from cache")
            return json.loads(response)
        else:
            print("Didn't receive from cache")
            action_results = self.get_action_results_generate()
            response = json.dumps(action_results)
            self.cacher.cache_file(
                self.story.seed, self.story.choices, response, "choices"
            )
            return action_results

    def generate_action_result(self, prompt, phrase, options=None):

        action_result = (
            phrase + " " + self.generator.generate(prompt + [phrase], options)
        )
        action, result = split_first_sentence(action_result)
        return action, result

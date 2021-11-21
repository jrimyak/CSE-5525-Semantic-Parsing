import copy

from lark import Tree, Token

from gpsr_command_understanding.grammar import CombineExpressions, tree_printer, DiscardVoid
from gpsr_command_understanding.util import get_placeholders, replace_child_in_tree, replace_words_in_tree, \
    has_placeholders
from gpsr_command_understanding.tokens import NonTerminal, WildCard, Anonymized, ROOT_SYMBOL
try:
    from queue import Queue as queue
except ImportError:
    from Queue import queue
from yieldfrom import yieldfrom, From, Return


def generate_sentences(start_tree, production_rules):
    """
    A generator that produces completely expanded sentences in depth-first order
    :param start_tree: the list of tokens to begin expanding
    :param production_rules: the rules to use for expanding the tokens
    """
    # Make sure the start point is a Tree
    if isinstance(start_tree, NonTerminal):
        stack = [Tree("expression", [start_tree])]
    elif isinstance(start_tree, list):
        stack = [Tree("expression", start_tree)]
    else:
        stack = [start_tree]

    while len(stack) != 0:
        sentence = stack.pop()
        replace_tokens = list(sentence.scan_values(lambda x: x in production_rules.keys()))
        if replace_tokens:
            replace_token = replace_tokens[0]
            # Replace it every way we know how
            for production in production_rules[replace_token]:
                modified_sentence = copy.deepcopy(sentence)
                replace_child_in_tree(modified_sentence, replace_token, production, only_once=True)
                # Generate the rest of the sentence recursively assuming this replacement
                stack.append(modified_sentence)
        else:
            # If we couldn't replace anything else, this sentence is done!
            sentence = CombineExpressions().visit(sentence)
            sentence = DiscardVoid().visit(sentence)
            yield sentence


def generate_random_pair(start_symbols, production_rules, semantics_rules, yield_requires_semantics=False, random_generator=None):
    return next(generate_sentence_parse_pairs(start_symbols, production_rules, semantics_rules, yield_requires_semantics=yield_requires_semantics, branch_cap=1, random_generator=random_generator))


def generate_sentence_parse_pairs(start_tree, production_rules, semantics_rules, start_semantics=None, yield_requires_semantics=True, branch_cap=None, random_generator=None):
    """
    Expand the start_symbols in breadth first order. At each expansion, see if we have an associated semantic template.
    If the current expansion has a semantics associated, also apply the expansion to the semantics.
    This is an efficient method of pairing the two grammars, but it only covers annotations that are carefully
    constructed to keep their head rule in the list of breadth first expansions of the utterance grammar.
    :param start_tree:
    :param production_rules:
    :param semantics_rules: dict mapping a sequence of tokens to a semantic template
    :param yield_requires_semantics: if true, will yield sentences that don't have associated semantics. Helpful for debugging.
    """
    """print(parsed.pretty())
    to_str = ToString()
    result = to_str.transform(parsed)
    print(result)"""

    # Make sure the start point is a Tree
    if isinstance(start_tree, NonTerminal):
        start_tree = Tree("expression", [start_tree])
    elif isinstance(start_tree, list):
        start_tree = Tree("expression", start_tree)
    else:
        assert isinstance(start_tree, Tree)

    frontier = queue()
    frontier.put((start_tree, start_semantics))
    while not frontier.empty():
        sentence, semantics = frontier.get()
        if not semantics:
            # Let's see if the  expansion is associated with any semantics
            semantics = semantics_rules.get(sentence)
        expansions = list(expand_pair(sentence, semantics, production_rules, branch_cap=branch_cap, random_generator=random_generator))
        if not expansions:
            # If we couldn't replace anything else, this sentence is done!
            if semantics:
                DiscardVoid().visit(semantics)
                CombineExpressions().visit(semantics)
                sem_placeholders_remaining = get_placeholders(semantics)
                sentence_placeholders_remaining = get_placeholders(sentence)
                # Are there placeholders in the semantics that aren't left in the sentence? These will never get expanded,
                # so it's almost certainly an error
                probably_should_be_filled = sem_placeholders_remaining.difference(sentence_placeholders_remaining)
                if len(probably_should_be_filled) > 0:
                    print("Unfilled placeholders {}".format(" ".join(map(str, probably_should_be_filled))))
                    print(tree_printer.transform(sentence))
                    print(tree_printer.transform(semantics))
                    print("This annotation is probably wrong")
                    print("")
                    continue
                elif len(sem_placeholders_remaining) != len(sentence_placeholders_remaining):
                    not_in_annotation = sentence_placeholders_remaining.difference(sem_placeholders_remaining)
                    print("Annotation is missing wildcards that are present in the original sentence. Were they left out accidentally?")
                    print(" ".join(map(str,not_in_annotation)))
                    print(tree_printer.transform(sentence))
                    print(tree_printer.transform(semantics))
                    print("")
            elif yield_requires_semantics:
                # This won't be a pair without semantics, so we'll just skip it
                continue
            yield (sentence, semantics)
            continue
        for pair in expansions:
            frontier.put(pair)

        # What productions don't have semantics?
        """if not modified_semantics:
            print(sentence_filled.pretty())
        """


def generate_sentence_slot_pairs(start_tree, production_rules, semantics_rules, start_semantics=None, yield_requires_semantics=True, branch_cap=None, random_generator=None):

    if isinstance(start_tree, NonTerminal):
        start_tree = Tree("expression", [start_tree])
    elif isinstance(start_tree, list):
        start_tree = Tree("expression", start_tree)
    else:
        assert isinstance(start_tree, Tree)

    frontier = Queue()
    frontier.put((start_tree, start_semantics))
    while not frontier.empty():
        sentence, semantics = frontier.get()
        #if not semantics:
        #    semantics = semantics_rules.get(sentence)
        #if semantics_rules.get(sentence):
        #    if semantics and semantics.children[0].data == "intent":
        #        semantics.children[1] = semantics_rules.get(sentence)
        #    else:
        #        semantics = semantics_rules.get(sentence)
            #print(semantics)

        expansions = list(expand_pair_slot(sentence, semantics, production_rules, semantics_rules, branch_cap=branch_cap, random_generator=random_generator))
        if not expansions:
            #print("Sentence: ", sentence.pretty())
            #print("Semantics: ", semantics.pretty())
            yield (sentence, semantics)
            #print(sentence)
            #print(semantics)
            #print(semantics.children[0].data)
            #print("---------------------")
            continue

        for pair in expansions:
            frontier.put(pair)


def expand_pair_full(sentence, semantics, production_rules, branch_cap=None, random_generator=None):
    return generate_sentence_parse_pairs(sentence, production_rules, {}, start_semantics=semantics,
                                       branch_cap=branch_cap, random_generator=random_generator)


def expand_pair(sentence, semantics, production_rules, branch_cap=None, random_generator=None):
        replace_token = list(sentence.scan_values(lambda x: x in production_rules.keys()))

        if not replace_token:
            return

        if random_generator:
            replace_token = random_generator.choice(replace_token)
            replacement_rules = production_rules[replace_token]
            if branch_cap:
                productions = random_generator.sample(replacement_rules, k=branch_cap)
            else:
                # Use all of the branches
                productions = production_rules[replace_token]
                random_generator.shuffle(productions)
        else:
            # We know we have at least one, so we'll just use the first
            replace_token = replace_token[0]
            productions = production_rules[replace_token]

        for production in productions:
            modified_sentence = copy.deepcopy(sentence)
            replace_child_in_tree(modified_sentence, replace_token, production, only_once=True)
            modified_sentence = DiscardVoid().visit(modified_sentence)

            # Normalize any chopped up text fragments to make sure we can pull semantics for these cases
            sentence_filled = CombineExpressions().visit(modified_sentence)
            # If we've got semantics for this expansion already, see if the replacements apply to them
            # For the basic annotation we provided, this should only happen when expanding ground terms
            
            modified_semantics = None
            if semantics:
                modified_semantics = copy.deepcopy(semantics)
                sem_substitute = production
                if isinstance(replace_token, WildCard) or (len(production.children) >0 and isinstance(production.children[0], Anonymized)):
                    sem_substitute = production.copy()
                    sem_substitute.children = ["\""] + sem_substitute.children + ["\""]
                replace_child_in_tree(modified_semantics, replace_token, sem_substitute)
            yield sentence_filled, modified_semantics


def expand_pair_slot(sentence, semantics, production_rules, semantics_rules, branch_cap=None, random_generator=None):
        #print("sentence: " + sentence.pretty())
        #if semantics:
        #    print("semantics: " + semantics.pretty())
        #else:
        #    print("semantics: None")

        replace_token = list(sentence.scan_values(lambda x: x in production_rules.keys()))

        if not replace_token:
            return

        if random_generator:
            replace_token = random_generator.choice(replace_token)
            replacement_rules = production_rules[replace_token]
            if branch_cap:
                productions = random_generator.sample(replacement_rules, k=min(branch_cap, len(replacement_rules)))
            else:
                # Use all of the branches
                productions = production_rules[replace_token]
                random_generator.shuffle(productions)
        else:
            # We know we have at least one, so we'll just use the first
            replace_token = replace_token[0]
            productions = production_rules[replace_token]

        #print("replace: ", replace_token)

        for production in productions:
            modified_sentence = copy.deepcopy(sentence)
            replace_child_in_tree(modified_sentence, replace_token, copy.deepcopy(production), only_once=True)
            modified_sentence = DiscardVoid().visit(modified_sentence)

            # Normalize any chopped up text fragments to make sure we can pull semantics for these cases
            sentence_filled = CombineExpressions().visit(modified_sentence)
            # If we've got semantics for this expansion already, see if the replacements apply to them
            # For the basic annotation we provided, this should only happen when expanding ground terms
            
            modified_semantics = None
            if semantics:
                modified_semantics = copy.deepcopy(semantics)

                sem_substitute = get_semantic_substitute(replace_token, copy.deepcopy(production), semantics_rules)

                if len(sem_substitute.children) > 0 and isinstance(sem_substitute.children[0], Tree) and sem_substitute.children[0].data == "intent":
                    #copy slot data
                    slot = Tree('expression', sem_substitute.children[1].children)
                    #replace with previous slot data
                    sem_substitute.children[1].children = [modified_semantics]
                    #now intent is the first child, with previous slot info
                    modified_semantics = sem_substitute
                    #replace the token in previous slot info with
                    replace_child_in_tree(modified_semantics, replace_token, slot, only_once=True)
                else:
                    replace_child_in_tree(modified_semantics, replace_token, sem_substitute, only_once=True)


                #print("replace_token", replace_token)
                #print("sem_substitute", sem_substitute.pretty())
            else:
                modified_semantics = get_semantic_substitute(replace_token, copy.deepcopy(production), semantics_rules)

            DiscardVoid().visit(modified_semantics)
            if isinstance(modified_semantics, Tree):
                CombineExpressions().visit(modified_semantics)
            #print(tree_printer(sentence_filled))
            #print(modified_semantics)
            yield sentence_filled, modified_semantics
            #print("-----------------------")


def get_semantic_substitute(replace_token, production, semantics_rules):
    
    sem_substitute = None
    sem_replace = semantics_rules.get(replace_token)
    if sem_replace:
        return copy.deepcopy(sem_replace)

    sem_production = semantics_rules.get(production)
    if sem_production:
        if (len(production.children) == 1) and isinstance(production.children[0], WildCard):
            pass
        else:
            return copy.deepcopy(sem_production)

    if isinstance(replace_token, WildCard):
        #print("expanding wildcard: ", replace_token)
        sem_replace_token = Tree('expression', [replace_token])
        sem = semantics_rules.get(sem_replace_token)

        return iob2_tagging(sem, production)

    sem_substitute = copy.deepcopy(production)
    replace_words_in_tree(sem_substitute, Token('WORD', 'O'))
    return sem_substitute


def iob2_tagging(sem, production):

    sem_substitute = Tree('expression', [])
    words = production.children[0].split(" ")

    if sem:
        sem = copy.deepcopy(sem.children[0])
        for i, word in enumerate(words):
            tag = Token('WORD', "B-" + sem) if i == 0 else Token('WORD', "I-" + sem)
            sem_substitute.children.append(tag)
    else:
        for i, word in enumerate(words):
            tag = Token('WORD', "O")
            sem_substitute.children.append(tag)
    
    return sem_substitute
    

@yieldfrom
def expand_all_semantics(production_rules, semantics_rules):
    """
    Expands all semantics rules
    :param production_rules:
    :param semantics_rules:
    """
    for utterance, parse in semantics_rules.items():
        yield From(generate_sentence_parse_pairs(utterance, production_rules, semantics_rules, False))


def pairs_without_placeholders(rules, semantics, only_in_grammar=False):
    pairs = expand_all_semantics(rules, semantics)
    out = {}
    all_utterances_in_grammar = set(generate_sentences(ROOT_SYMBOL, rules))
    for command, parse in pairs:
        if has_placeholders(command) or has_placeholders(parse):
            # This case is almost certainly a bug with the annotations
            print("Skipping pair for {} because it still has placeholders after expansion".format(
                tree_printer(command)))
            continue
        # If it's important that we only get pairs that are in the grammar, check to make sure
        if only_in_grammar and not command in all_utterances_in_grammar:
            continue
        out[tree_printer(command)] = tree_printer(parse)
    return out
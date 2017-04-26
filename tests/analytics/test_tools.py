from analytics.tools import diff_json, own_by, diff_json_key


def test_diff_json_simple():
    json1 = {'name': 'toto'}
    json2 = {'name': 'titi'}
    diff = diff_json(json1, json2)
    assert len(diff) == 2


def test_diff_json_key_simple():
    json1 = {'name': 'toto'}
    json2 = {'name': 'titi'}
    diff = diff_json_key(json1, json2)
    assert len(diff) == 1


def test_diff_json_equal():
    json1 = {'name': 'toto'}
    json2 = {'name': 'toto'}
    diff = diff_json(json1, json2)
    assert len(diff) == 0


def test_diff_json_key_equal():
    json1 = {'name': 'toto'}
    json2 = {'name': 'toto'}
    diff = diff_json_key(json1, json2)
    assert len(diff) == 0


def test_diff_json_more_key():
    json1 = {'name': 'toto', 'first_name': 'tutu'}
    json2 = {'name': 'toto'}
    diff = diff_json(json1, json2)
    assert len(diff) == 1


def test_diff_json_list():
    json1 = {'name': 'toto', 'first_name': 'tutu', "hobby": ["foot", "swim", "rugby", "manga"]}
    json2 = {'name': 'toto', 'first_name': 'tutu', "hobby": ["foot", "basket", "rugby"]}
    diff = diff_json(json1, json2)
    assert len(diff) == 3


def test_diff_json_inner_dict():
    json1 = {'name': 'toto', 'first_name': 'tutu', "hobby": {
        "sport": ["foot", "swim", "rugby"], "game": "pokemon"}}
    json2 = {'name': 'toto', 'first_name': 'tutu', "hobby": {
        "sport": ["foot", "basket", "rugby"], "game": "pokemon"}}
    diff = diff_json(json1, json2)
    assert len(diff) == 2


def test_own_by_inner_dict():
    json1 = {'name': 'toto', 'first_name': 'tutu', "hobby": {
        "sport": ["foot", "basket", "rugby", "NOTaSPORT"], "game": "pokemon"}}
    json2 = {'name': 'toto', 'first_name': 'tutu', "hobby": {
        "sport": ["foot", "basket", "rugby"], "game": "pokemon"}}
    diff = diff_json_key(json1, json2)
    assert len(diff) == 1
    assert own_by(diff[0], json1)
    assert not own_by(diff[0], json2)


def test_big_json_equal():
    json1 = [
        {
            "_id": "5710c3749ada8bf1a347048f",
            "index": 0,
            "guid": "8afca42d-0f60-4c3d-afe5-154c88629f82",
            "isActive": True,
            "balance": "$3,051.88",
            "picture": "http://placehold.it/32x32",
            "age": 29,
            "eyeColor": "brown",
            "name": {
                "first": "Alexandra",
                "last": "Duran"
            },
            "company": "TURNLING",
            "email": "alexandra.duran@turnling.info",
            "phone": "+1 (864) 516-3247",
            "address": "169 Hicks Street, Bentley, Ohio, 7411",
            "about": "Ea esse eiusmod irure sit dolor labore sunt consectetur. In voluptate nisi irure magna adipisicing minim deserunt nostrud Lorem amet cillum exercitation enim. Lorem non eiusmod magna dolor minim et nisi culpa enim proident cupidatat incididunt eiusmod anim. Sit tempor adipisicing minim laborum.",
            "registered": "Sunday, September 6, 2015 11:55 AM",
            "latitude": "-86.389572",
            "longitude": "62.317355",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Alexandra! You have 9 unread messages.",
            "favoriteFruit": "apple"
        },
        {
            "_id": "5710c3742a06bcbd2d63230f",
            "index": 1,
            "guid": "3de7f06e-f20c-4030-abc3-832001a7e717",
            "isActive": False,
            "balance": "$1,755.51",
            "picture": "http://placehold.it/32x32",
            "age": 33,
            "eyeColor": "green",
            "name": {
                "first": "Bernadette",
                "last": "Barron"
            },
            "company": "VITRICOMP",
            "email": "bernadette.barron@vitricomp.us",
            "phone": "+1 (924) 464-2503",
            "address": "514 Provost Street, Stouchsburg, Alabama, 7746",
            "about": "Ad ut do minim nulla elit aliquip elit anim dolore aliquip id nostrud consectetur. Quis duis amet veniam aute irure quis. Culpa cupidatat aute deserunt non veniam consectetur eiusmod consequat id amet laborum deserunt. Tempor adipisicing occaecat et id ea sint. Dolor exercitation nostrud duis consequat mollit occaecat.",
            "registered": "Wednesday, April 16, 2014 6:17 AM",
            "latitude": "71.884742",
            "longitude": "88.13236",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Bernadette! You have 7 unread messages.",
            "favoriteFruit": "banana"
        },
        {
            "_id": "5710c3749c4ff6abf021ef3e",
            "index": 2,
            "guid": "ece099df-5731-46cc-a84b-252ca464e8ba",
            "isActive": True,
            "balance": "$2,109.55",
            "picture": "http://placehold.it/32x32",
            "age": 23,
            "eyeColor": "brown",
            "name": {
                "first": "Isabel",
                "last": "Morris"
            },
            "company": "TRANSLINK",
            "email": "isabel.morris@translink.net",
            "phone": "+1 (964) 578-2956",
            "address": "932 Narrows Avenue, Corriganville, Texas, 1150",
            "about": "Occaecat esse sunt non ipsum fugiat irure eiusmod velit adipisicing. Eu id sit excepteur nisi ex ex proident voluptate duis non adipisicing sint veniam voluptate. Reprehenderit adipisicing nulla aliqua pariatur esse enim.",
            "registered": "Wednesday, September 2, 2015 9:31 AM",
            "latitude": "-26.803574",
            "longitude": "102.279397",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Isabel! You have 6 unread messages.",
            "favoriteFruit": "strawberry"
        },
        {
            "_id": "5710c3743947c1a15c4eeb05",
            "index": 3,
            "guid": "29c4d75b-7e8b-48eb-b064-1c46cc2fd4c8",
            "isActive": True,
            "balance": "$1,289.18",
            "picture": "http://placehold.it/32x32",
            "age": 26,
            "eyeColor": "blue",
            "name": {
                "first": "Head",
                "last": "Herman"
            },
            "company": "EURON",
            "email": "head.herman@euron.biz",
            "phone": "+1 (894) 419-2102",
            "address": "885 Euclid Avenue, Beaulieu, Georgia, 8535",
            "about": "Fugiat duis pariatur Lorem excepteur sit. Aute do non esse sunt minim. Minim eiusmod dolore occaecat do eu aliqua. Reprehenderit non cillum eiusmod ullamco incididunt laborum irure culpa. Cupidatat enim quis esse sunt velit qui ipsum commodo aliquip irure ut. Non adipisicing esse eu nulla cupidatat enim ipsum.",
            "registered": "Friday, February 21, 2014 12:56 AM",
            "latitude": "-26.767073",
            "longitude": "-99.914782",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Head! You have 5 unread messages.",
            "favoriteFruit": "strawberry"
        },
        {
            "_id": "5710c37422a2bac7090f75f8",
            "index": 4,
            "guid": "58572bff-82f0-448d-9539-975417a48686",
            "isActive": True,
            "balance": "$3,579.35",
            "picture": "http://placehold.it/32x32",
            "age": 20,
            "eyeColor": "green",
            "name": {
                "first": "Bean",
                "last": "Stokes"
            },
            "company": "VETRON",
            "email": "bean.stokes@vetron.com",
            "phone": "+1 (853) 410-2211",
            "address": "945 Preston Court, Bainbridge, Nevada, 818",
            "about": "Veniam nisi laboris fugiat magna ipsum laborum eu amet exercitation et eiusmod do. Ex cillum esse eu veniam laboris nisi duis sit ullamco qui anim consequat. Amet nulla proident sunt ipsum ullamco veniam cillum enim ipsum ea cupidatat. Cupidatat sit cupidatat consequat esse irure aute. Nulla Lorem excepteur esse aute laborum do dolore aute reprehenderit tempor minim.",
            "registered": "Friday, July 3, 2015 2:52 PM",
            "latitude": "-76.678541",
            "longitude": "76.328586",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Bean! You have 6 unread messages.",
            "favoriteFruit": "apple"
        }
    ]
    json2 = [
        {
            "_id": "5710c3749ada8bf1a347048f",
            "index": 0,
            "guid": "8afca42d-0f60-4c3d-afe5-154c88629f82",
            "isActive": True,
            "balance": "$3,051.88",
            "picture": "http://placehold.it/32x32",
            "age": 29,
            "eyeColor": "brown",
            "name": {
                "first": "Alexandra",
                "last": "Duran"
            },
            "company": "TURNLING",
            "email": "alexandra.duran@turnling.info",
            "phone": "+1 (864) 516-3247",
            "address": "169 Hicks Street, Bentley, Ohio, 7411",
            "about": "Ea esse eiusmod irure sit dolor labore sunt consectetur. In voluptate nisi irure magna adipisicing minim deserunt nostrud Lorem amet cillum exercitation enim. Lorem non eiusmod magna dolor minim et nisi culpa enim proident cupidatat incididunt eiusmod anim. Sit tempor adipisicing minim laborum.",
            "registered": "Sunday, September 6, 2015 11:55 AM",
            "latitude": "-86.389572",
            "longitude": "62.317355",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Alexandra! You have 9 unread messages.",
            "favoriteFruit": "apple"
        },
        {
            "_id": "5710c3742a06bcbd2d63230f",
            "index": 1,
            "guid": "3de7f06e-f20c-4030-abc3-832001a7e717",
            "isActive": False,
            "balance": "$1,755.51",
            "picture": "http://placehold.it/32x32",
            "age": 33,
            "eyeColor": "green",
            "name": {
                "first": "Bernadette",
                "last": "Barron"
            },
            "company": "VITRICOMP",
            "email": "bernadette.barron@vitricomp.us",
            "phone": "+1 (924) 464-2503",
            "address": "514 Provost Street, Stouchsburg, Alabama, 7746",
            "about": "Ad ut do minim nulla elit aliquip elit anim dolore aliquip id nostrud consectetur. Quis duis amet veniam aute irure quis. Culpa cupidatat aute deserunt non veniam consectetur eiusmod consequat id amet laborum deserunt. Tempor adipisicing occaecat et id ea sint. Dolor exercitation nostrud duis consequat mollit occaecat.",
            "registered": "Wednesday, April 16, 2014 6:17 AM",
            "latitude": "71.884742",
            "longitude": "88.13236",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Bernadette! You have 7 unread messages.",
            "favoriteFruit": "banana"
        },
        {
            "_id": "5710c3749c4ff6abf021ef3e",
            "index": 2,
            "guid": "ece099df-5731-46cc-a84b-252ca464e8ba",
            "isActive": True,
            "balance": "$2,109.55",
            "picture": "http://placehold.it/32x32",
            "age": 23,
            "eyeColor": "brown",
            "name": {
                "first": "Isabel",
                "last": "Morris"
            },
            "company": "TRANSLINK",
            "email": "isabel.morris@translink.net",
            "phone": "+1 (964) 578-2956",
            "address": "932 Narrows Avenue, Corriganville, Texas, 1150",
            "about": "Occaecat esse sunt non ipsum fugiat irure eiusmod velit adipisicing. Eu id sit excepteur nisi ex ex proident voluptate duis non adipisicing sint veniam voluptate. Reprehenderit adipisicing nulla aliqua pariatur esse enim.",
            "registered": "Wednesday, September 2, 2015 9:31 AM",
            "latitude": "-26.803574",
            "longitude": "102.279397",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Isabel! You have 6 unread messages.",
            "favoriteFruit": "strawberry"
        },
        {
            "_id": "5710c3743947c1a15c4eeb05",
            "index": 3,
            "guid": "29c4d75b-7e8b-48eb-b064-1c46cc2fd4c8",
            "isActive": True,
            "balance": "$1,289.18",
            "picture": "http://placehold.it/32x32",
            "age": 26,
            "eyeColor": "blue",
            "name": {
                "first": "Head",
                "last": "Herman"
            },
            "company": "EURON",
            "email": "head.herman@euron.biz",
            "phone": "+1 (894) 419-2102",
            "address": "885 Euclid Avenue, Beaulieu, Georgia, 8535",
            "about": "Fugiat duis pariatur Lorem excepteur sit. Aute do non esse sunt minim. Minim eiusmod dolore occaecat do eu aliqua. Reprehenderit non cillum eiusmod ullamco incididunt laborum irure culpa. Cupidatat enim quis esse sunt velit qui ipsum commodo aliquip irure ut. Non adipisicing esse eu nulla cupidatat enim ipsum.",
            "registered": "Friday, February 21, 2014 12:56 AM",
            "latitude": "-26.767073",
            "longitude": "-99.914782",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Head! You have 5 unread messages.",
            "favoriteFruit": "strawberry"
        },
        {
            "_id": "5710c37422a2bac7090f75f8",
            "index": 4,
            "guid": "58572bff-82f0-448d-9539-975417a48686",
            "isActive": True,
            "balance": "$3,579.35",
            "picture": "http://placehold.it/32x32",
            "age": 20,
            "eyeColor": "green",
            "name": {
                "first": "Bean",
                "last": "Stokes"
            },
            "company": "VETRON",
            "email": "bean.stokes@vetron.com",
            "phone": "+1 (853) 410-2211",
            "address": "945 Preston Court, Bainbridge, Nevada, 818",
            "about": "Veniam nisi laboris fugiat magna ipsum laborum eu amet exercitation et eiusmod do. Ex cillum esse eu veniam laboris nisi duis sit ullamco qui anim consequat. Amet nulla proident sunt ipsum ullamco veniam cillum enim ipsum ea cupidatat. Cupidatat sit cupidatat consequat esse irure aute. Nulla Lorem excepteur esse aute laborum do dolore aute reprehenderit tempor minim.",
            "registered": "Friday, July 3, 2015 2:52 PM",
            "latitude": "-76.678541",
            "longitude": "76.328586",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Bean! You have 6 unread messages.",
            "favoriteFruit": "apple"
        }
    ]
    diff = diff_json(json1, json2)
    assert len(diff) == 0


def test_big_json_equal():
    json1 = [
        {
            "_id": "5710c3749ada8bf1a347048f",
            "index": 0,
            "guid": "8afca42d-0f60-4c3d-afe5-154c88629f82",
            "isActive": True,
            "balance": "$3,051.88",
            "picture": "http://placehold.it/32x32",
            "age": 29,
            "eyeColor": "brown",
            "name": {
                "first": "Alexandra",
                "last": "Duran"
            },
            "company": "TURNLING",
            "email": "alexandra.duran@turnling.info",
            "phone": "+1 (864) 516-3247",
            "address": "169 Hicks Street, Bentley, Ohio, 7411",
            "about": "Ea esse eiusmod irure sit dolor labore sunt consectetur. In voluptate nisi irure magna adipisicing minim deserunt nostrud Lorem amet cillum exercitation enim. Lorem non eiusmod magna dolor minim et nisi culpa enim proident cupidatat incididunt eiusmod anim. Sit tempor adipisicing minim laborum.",
            "registered": "Sunday, September 6, 2015 11:55 AM",
            "latitude": "-86.389572",
            "longitude": "62.317355",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Alexandra! You have 9 unread messages.",
            "favoriteFruit": "apple"
        },
        {
            "_id": "5710c3742a06bcbd2d63230f",
            "index": 1,
            "guid": "3de7f06e-f20c-4030-abc3-832001a7e717",
            "isActive": False,
            "balance": "$1,755.51",
            "picture": "http://placehold.it/32x32",
            "age": 33,
            "eyeColor": "green",
            "name": {
                "first": "Bernadette",
                "last": "Barron"
            },
            "company": "VITRICOMP",
            "email": "bernadette.barron@vitricomp.us",
            "phone": "+1 (924) 464-2503",
            "address": "514 Provost Street, Stouchsburg, Alabama, 7746",
            "about": "Ad ut do minim nulla elit aliquip elit anim dolore aliquip id nostrud consectetur. Quis duis amet veniam aute irure quis. Culpa cupidatat aute deserunt non veniam consectetur eiusmod consequat id amet laborum deserunt. Tempor adipisicing occaecat et id ea sint. Dolor exercitation nostrud duis consequat mollit occaecat.",
            "registered": "Wednesday, April 16, 2014 6:17 AM",
            "latitude": "71.884742",
            "longitude": "88.13236",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Bernadette! You have 7 unread messages.",
            "favoriteFruit": "banana"
        },
        {
            "_id": "5710c3749c4ff6abf021ef3e",
            "index": 2,
            "guid": "ece099df-5731-46cc-a84b-252ca464e8ba",
            "isActive": True,
            "balance": "$2,109.55",
            "picture": "http://placehold.it/32x32",
            "age": 23,
            "eyeColor": "brown",
            "name": {
                "first": "Isabel",
                "last": "Morris"
            },
            "company": "TRANSLINK",
            "email": "isabel.morris@translink.net",
            "phone": "+1 (964) 578-2956",
            "address": "932 Narrows Avenue, Corriganville, Texas, 1150",
            "about": "Occaecat esse sunt non ipsum fugiat irure eiusmod velit adipisicing. Eu id sit excepteur nisi ex ex proident voluptate duis non adipisicing sint veniam voluptate. Reprehenderit adipisicing nulla aliqua pariatur esse enim.",
            "registered": "Wednesday, September 2, 2015 9:31 AM",
            "latitude": "-26.803574",
            "longitude": "102.279397",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Isabel! You have 6 unread messages.",
            "favoriteFruit": "strawberry"
        },
        {
            "_id": "5710c3743947c1a15c4eeb05",
            "index": 3,
            "guid": "29c4d75b-7e8b-48eb-b064-1c46cc2fd4c8",
            "isActive": True,
            "balance": "$1,289.18",
            "picture": "http://placehold.it/32x32",
            "age": 26,
            "eyeColor": "blue",
            "name": {
                "first": "Head",
                "last": "Herman"
            },
            "company": "EURON",
            "email": "head.herman@euron.biz",
            "phone": "+1 (894) 419-2102",
            "address": "885 Euclid Avenue, Beaulieu, Georgia, 8535",
            "about": "Fugiat duis pariatur Lorem excepteur sit. Aute do non esse sunt minim. Minim eiusmod dolore occaecat do eu aliqua. Reprehenderit non cillum eiusmod ullamco incididunt laborum irure culpa. Cupidatat enim quis esse sunt velit qui ipsum commodo aliquip irure ut. Non adipisicing esse eu nulla cupidatat enim ipsum.",
            "registered": "Friday, February 21, 2014 12:56 AM",
            "latitude": "-26.767073",
            "longitude": "-99.914782",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Head! You have 5 unread messages.",
            "favoriteFruit": "strawberry"
        },
        {
            "_id": "5710c37422a2bac7090f75f8",
            "index": 4,
            "guid": "58572bff-82f0-448d-9539-975417a48686",
            "isActive": True,
            "balance": "$3,579.35",
            "picture": "http://placehold.it/32x32",
            "age": 20,
            "eyeColor": "green",
            "name": {
                "first": "Bean",
                "last": "Stokes"
            },
            "company": "VETRON",
            "email": "bean.stokes@vetron.com",
            "phone": "+1 (853) 410-2211",
            "address": "945 Preston Court, Bainbridge, Nevada, 818",
            "about": "Veniam nisi laboris fugiat magna ipsum laborum eu amet exercitation et eiusmod do. Ex cillum esse eu veniam laboris nisi duis sit ullamco qui anim consequat. Amet nulla proident sunt ipsum ullamco veniam cillum enim ipsum ea cupidatat. Cupidatat sit cupidatat consequat esse irure aute. Nulla Lorem excepteur esse aute laborum do dolore aute reprehenderit tempor minim.",
            "registered": "Friday, July 3, 2015 2:52 PM",
            "latitude": "-76.678541",
            "longitude": "76.328586",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Bean! You have 6 unread messages.",
            "favoriteFruit": "apple"
        }
    ]
    json2 = [
        {
            "_id": "5710c3749ada8bf1a347048f",
            "index": 0,
            "guid": "8afca42d-0f60-4c3d-afe5-154c88629f82",
            "isActive": True,
            "balance": "$3,051.88",
            "picture": "http://placehold.it/32x32",
            "age": 29,
            "eyeColor": "brown",
            "name": {
                "first": "Alexandra",
                "last": "Duran"
            },
            "company": "TURNLING",
            "email": "alexandra.duran@turnling.info",
            "phone": "+1 (864) 516-3247",
            "address": "169 Hicks Street, Bentley, Ohio, 7411",
            "about": "Ea esse eiusmod irure sit dolor labore sunt consectetur. In voluptate nisi irure magna adipisicing minim deserunt nostrud Lorem amet cillum exercitation enim. Lorem non eiusmod magna dolor minim et nisi culpa enim proident cupidatat incididunt eiusmod anim. Sit tempor adipisicing minim laborum.",
            "registered": "Sunday, September 6, 2015 11:55 AM",
            "latitude": "-86.389572",
            "longitude": "62.317355",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Alexandra! You have 9 unread messages.",
            "favoriteFruit": "apple"
        },
        {
            "_id": "5710c3742a06bcbd2d63230f",
            "index": 1,
            "guid": "3de7f06e-f20c-4030-abc3-832001a7e717",
            "isActive": False,
            "balance": "$1,755.51",
            "picture": "http://placehold.it/32x32",
            "age": 33,
            "eyeColor": "green",
            "name": {
                "first": "Bernadette",
                "last": "Barron",
                "nick": "Barron"
            },
            "company": "VITRICOMP",
            "email": "bernadette.barron@vitricomp.us",
            "phone": "+1 (924) 464-2503",
            "address": "514 Provost Street, Stouchsburg, Alabama, 7746",
            "about": "Ad ut do minim nulla elit aliquip elit anim dolore aliquip id nostrud consectetur. Quis duis amet veniam aute irure quis. Culpa cupidatat aute deserunt non veniam consectetur eiusmod consequat id amet laborum deserunt. Tempor adipisicing occaecat et id ea sint. Dolor exercitation nostrud duis consequat mollit occaecat.",
            "registered": "Wednesday, April 16, 2014 6:17 AM",
            "latitude": "71.884742",
            "longitude": "88.13236",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Bernadette! You have 7 unread messages.",
            "favoriteFruit": "banana"
        },
        {
            "_id": "5710c3749c4ff6abf021ef3e",
            "index": 2,
            "guid": "ece099df-5731-46cc-a84b-252ca464e8ba",
            "isActive": True,
            "balance": "$2,109.55",
            "picture": "http://placehold.it/32x32",
            "age": 23,
            "eyeColor": "brown",
            "name": {
                "first": "Isabel",
                "last": "Morris"
            },
            "company": "TRANSLINK",
            "email": "isabel.morris@translink.net",
            "phone": "+1 (964) 578-2956",
            "address": "932 Narrows Avenue, Corriganville, Texas, 1150",
            "about": "Occaecat esse sunt non ipsum fugiat irure eiusmod velit adipisicing. Eu id sit excepteur nisi ex ex proident voluptate duis non adipisicing sint veniam voluptate. Reprehenderit adipisicing nulla aliqua pariatur esse enim.",
            "registered": "Wednesday, September 2, 2015 9:31 AM",
            "latitude": "-26.803574",
            "longitude": "102.279397",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Isabel! You have 6 unread messages.",
            "favoriteFruit": "strawberry"
        },
        {
            "_id": "5710c3743947c1a15c4eeb05",
            "index": 3,
            "guid": "29c4d75b-7e8b-48eb-b064-1c46cc2fd4c8",
            "isActive": True,
            "balance": "$1,289.18",
            "picture": "http://placehold.it/32x32",
            "age": 26,
            "eyeColor": "blue",
            "name": {
                "first": "Head",
                "last": "Herman"
            },
            "company": "EURON",
            "email": "head.herman@euron.biz",
            "phone": "+1 (894) 419-2102",
            "address": "885 Euclid Avenue, Beaulieu, Georgia, 8535",
            "about": "Fugiat duis pariatur Lorem excepteur sit. Aute do non esse sunt minim. Minim eiusmod dolore occaecat do eu aliqua. Reprehenderit non cillum eiusmod ullamco incididunt laborum irure culpa. Cupidatat enim quis esse sunt velit qui ipsum commodo aliquip irure ut. Non adipisicing esse eu nulla cupidatat enim ipsum.",
            "registered": "Friday, February 21, 2014 12:56 AM",
            "latitude": "-26.767073",
            "longitude": "-99.914782",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Head! You have 5 unread messages.",
            "favoriteFruit": "strawberry"
        },
        {
            "_id": "5710c37422a2bac7090f75f8",
            "index": 4,
            "guid": "58572bff-82f0-448d-9539-975417a48686",
            "isActive": True,
            "balance": "$3,579.35",
            "picture": "http://placehold.it/32x32",
            "age": 20,
            "eyeColor": "green",
            "name": {
                "first": "Bean",
                "last": "Stokes",
                "pouet": 'toto'
            },
            "company": "VETRON",
            "email": "bean.stokes@vetron.com",
            "phone": "+1 (853) 410-2211",
            "address": "945 Preston Court, Bainbridge, Nevada, 818",
            "about": "Veniam nisi laboris fugiat magna ipsum laborum eu amet exercitation et eiusmod do. Ex cillum esse eu veniam laboris nisi duis sit ullamco qui anim consequat. Amet nulla proident sunt ipsum ullamco veniam cillum enim ipsum ea cupidatat. Cupidatat sit cupidatat consequat esse irure aute. Nulla Lorem excepteur esse aute laborum do dolore aute reprehenderit tempor minim.",
            "registered": "Friday, July 3, 2015 2:52 PM",
            "latitude": "-76.678541",
            "longitude": "76.328586",
            "tags": [
                7,
                "aliquip"
            ],
            "range": [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9
            ],
            "friends": [
                3,
                {
                    "id": 1,
                    "name": "Malone Martinez"
                },
                {
                    "id": 1,
                    "name": "Malone Martinez"
                }
            ],
            "greeting": "Hello, Bean! You have 6 unread messages.",
            "favoriteFruit": "apple"
        }
    ]
    diff = diff_json(json1, json2)
    assert len(diff) == 4

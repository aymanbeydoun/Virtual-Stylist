import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { FamilyIcon, HangerIcon, PersonIcon, SparkIcon } from "@/components/icons";
import { useAuth } from "@/state/auth";
import { useAccent } from "@/state/theme";
import { fonts, palette } from "@/theme";
import { AddItemScreen } from "@/screens/Closet/AddItemScreen";
import { ClosetScreen } from "@/screens/Closet/ClosetScreen";
import { ItemDetailScreen } from "@/screens/Closet/ItemDetailScreen";
import { FamilyScreen } from "@/screens/Family/FamilyScreen";
import { AddMemberScreen } from "@/screens/Family/AddMemberScreen";
import { SignInScreen } from "@/screens/Auth/SignInScreen";
import { StyleScreen } from "@/screens/Style/StyleScreen";
import { OutfitDetailScreen } from "@/screens/Style/OutfitDetailScreen";
import { StatusScreen } from "@/screens/Status/StatusScreen";
import { StylistChatScreen } from "@/screens/Chat/StylistChatScreen";
import { YouScreen } from "@/screens/You/YouScreen";

export type RootStackParamList = {
  Tabs: undefined;
  AddItem: undefined;
  ItemDetail: { itemId: string };
  AddMember: undefined;
  OutfitDetail: { outfitId: string };
  Status: undefined;
  StylistChat: { outfitId?: string; context?: string };
  SignIn: undefined;
};

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator<RootStackParamList>();

function Tabs() {
  const activeColor = useAccent().color;
  return (
    <Tab.Navigator
      sceneContainerStyle={{ backgroundColor: "transparent" }}
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: activeColor,
        tabBarInactiveTintColor: palette.textMuted,
        tabBarLabelStyle: { fontFamily: fonts.mono, fontSize: 9.5, letterSpacing: 1 },
        tabBarStyle: {
          backgroundColor: "rgba(10,11,14,0.94)",
          borderTopWidth: 1,
          borderTopColor: palette.hairlineFaint,
        },
      }}
    >
      <Tab.Screen
        name="Closet"
        component={ClosetScreen}
        options={{ tabBarIcon: ({ color }) => <HangerIcon size={21} color={color} /> }}
      />
      <Tab.Screen
        name="Style"
        component={StyleScreen}
        options={{ tabBarIcon: ({ color }) => <SparkIcon size={21} color={color} /> }}
      />
      <Tab.Screen
        name="Family"
        component={FamilyScreen}
        options={{ tabBarIcon: ({ color }) => <FamilyIcon size={21} color={color} /> }}
      />
      <Tab.Screen
        name="You"
        component={YouScreen}
        options={{ tabBarIcon: ({ color }) => <PersonIcon size={21} color={color} /> }}
      />
    </Tab.Navigator>
  );
}

export function RootNavigator() {
  const signedIn = useAuth((s) => s.devUserId !== null);
  return (
    <Stack.Navigator
      screenOptions={{
        contentStyle: { backgroundColor: "transparent" },
        headerStyle: { backgroundColor: "transparent" },
        headerTintColor: palette.text,
        headerTitleStyle: { fontFamily: fonts.bodyBold, fontSize: 15 },
        headerShadowVisible: false,
      }}
    >
      {!signedIn ? (
        <Stack.Screen name="SignIn" component={SignInScreen} options={{ headerShown: false }} />
      ) : (
        <>
          <Stack.Screen name="Tabs" component={Tabs} options={{ headerShown: false }} />
          <Stack.Screen name="AddItem" component={AddItemScreen} options={{ title: "Add item" }} />
          <Stack.Screen name="ItemDetail" component={ItemDetailScreen} options={{ title: "Item" }} />
          <Stack.Screen name="AddMember" component={AddMemberScreen} options={{ title: "Add family member" }} />
          <Stack.Screen
            name="OutfitDetail"
            component={OutfitDetailScreen}
            options={{ title: "Outfit" }}
          />
          <Stack.Screen
            name="Status"
            component={StatusScreen}
            options={{ title: "Status" }}
          />
          <Stack.Screen
            name="StylistChat"
            component={StylistChatScreen}
            options={{ title: "Chat" }}
          />
        </>
      )}
    </Stack.Navigator>
  );
}
